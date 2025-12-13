import serial
import threading
import time
import csv
from datetime import datetime

from nicegui import ui
import pandas as pd
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import os

# ==========================
# CONFIGURAÇÕES GERAIS
# ==========================
PORTA_SERIAL = 'COM2'
BAUDRATE = 115200
TIMEOUT = 1

ARQUIVO_CSV = 'historico_medicoes.csv'

rodando = True

estado = {
    'rpm': 0.0,
    'temperatura': 0.0,
    'tensao': 0.0,
    'corrente': 0.0,
    'ultima_linha': '',
    'historico': [],  # lista de dicts: {ts, rpm, temperatura, tensao, corrente}
}

lock = threading.Lock()


# ==========================
# LEITURA DA SERIAL
# ==========================
def parse_linha(linha: str):
    """
    Espera algo no formato:
    RPM: 0.00 || Temperatura: 50.29 || Tensao: 1.24 || Corrente: 2.70
    """
    try:
        partes = [p.strip() for p in linha.split("||")]
        if len(partes) < 4:
            raise ValueError("Linha incompleta")

        rpm_txt = partes[0]
        temp_txt = partes[1]
        tensao_txt = partes[2]
        corrente_txt = partes[3]

        rpm = float(rpm_txt.split(':')[1])
        temperatura = float(temp_txt.split(':')[1])
        tensao = float(tensao_txt.split(':')[1])
        corrente = float(corrente_txt.split(':')[1])

        return rpm, temperatura, tensao, corrente

    except Exception as e:
        print('[PARSE] Erro ao interpretar linha:', linha, '| Erro:', e)
        return None, None, None, None


def thread_serial():
    global rodando
    try:
        with serial.Serial(PORTA_SERIAL, BAUDRATE, timeout=TIMEOUT) as ser:
            print(f'[SERIAL] Porta {PORTA_SERIAL} aberta.')

            # Cria CSV com cabeçalho, se ainda não existir
            try:
                with open(ARQUIVO_CSV, 'x', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'rpm', 'temperatura', 'tensao', 'corrente'])
            except FileExistsError:
                pass

            while rodando:
                linha = ser.readline().decode(errors='ignore').strip()
                if not linha:
                    continue

                rpm, temperatura, tensao, corrente = parse_linha(linha)
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with lock:
                    estado['ultima_linha'] = linha

                    if rpm is not None:
                        estado['rpm'] = rpm
                        estado['temperatura'] = temperatura
                        estado['tensao'] = tensao
                        estado['corrente'] = corrente

                        estado['historico'].append({
                            'ts': ts,
                            'rpm': rpm,
                            'temperatura': temperatura,
                            'tensao': tensao,
                            'corrente': corrente,
                        })

                if rpm is not None:
                    with open(ARQUIVO_CSV, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([ts, rpm, temperatura, tensao, corrente])

    except serial.SerialException as e:
        print(f'[SERIAL] Erro: {e}')
    finally:
        print('[SERIAL] Thread finalizada.')


t = threading.Thread(target=thread_serial, daemon=True)
t.start()


# ==========================
# ESTILO GLOBAL (AGORA VIA FUNÇÃO)
# ==========================
def aplicar_tema():
    """Configura tema e fundo: chamado dentro das páginas, NÃO no global."""
    ui.colors(primary='#2563eb')
    ui.add_head_html("""
    <style>
      body {
        background-color: #f3f4f6; /* cinza claro */
      }
    </style>
    """)


# ==========================
# MENU SUPERIOR
# ==========================
def menu():
    with ui.header().classes('items-center justify-between px-6 py-2 bg-white shadow-sm'):
        with ui.row().classes('items-center gap-3'):
            ui.icon('speed').classes('text-primary text-2xl')
            ui.label('Supervisório - Bancada de Testes').classes('text-lg font-bold text-gray-800')

        with ui.row().classes('gap-2'):
            ui.button('Dashboard', on_click=lambda: ui.navigate.to('/')) \
                .classes('bg-primary text-white text-sm px-3 py-1 rounded-lg')
            ui.button('Calibração/Testes', on_click=lambda: ui.navigate.to('/calibracao')) \
                .classes('text-primary text-sm')
            ui.button('Relatórios', on_click=lambda: ui.navigate.to('/relatorios')) \
                .classes('text-primary text-sm')
            ui.button('Histórico', on_click=lambda: ui.navigate.to('/historico')) \
                .classes('text-primary text-sm')
            ui.button('Configurações', on_click=lambda: ui.navigate.to('/configuracoes')) \
                .classes('text-primary text-sm')
            ui.button('Resumo da Sessão', on_click=lambda: ui.navigate.to('/resumo')) \
                .classes('text-primary text-sm')
            ui.button('Manutenção/Testes', on_click=lambda: ui.navigate.to('/manutencao')) \
                .classes('text-primary text-sm')
            ui.button('Ajuda/Créditos', on_click=lambda: ui.navigate.to('/ajuda')) \
                .classes('text-primary text-sm')


# ==========================
# FUNÇÕES DE RELATÓRIO (EXCEL/PDF)
# ==========================
def gerar_excel():
    with lock:
        hist = estado['historico'][:]

    if not hist:
        return ui.notify("Sem dados para exportar!", color='negative')

    df = pd.DataFrame(hist)
    arquivo = "relatorio.xlsx"
    df.to_excel(arquivo, index=False)

    ui.download(arquivo)


def gerar_pdf():
    with lock:
        hist = estado['historico'][:]

    if not hist:
        return ui.notify("Sem dados para exportar!", color='negative')

    tempos = [h['ts'] for h in hist]
    rpms = [h['rpm'] for h in hist]
    temperaturas = [h['temperatura'] for h in hist]

    # 1) GRÁFICO PNG (RPM)
    plt.figure(figsize=(10, 4))
    plt.plot(rpms, linewidth=2)
    plt.title("RPM ao longo da sessão")
    plt.xlabel("Amostra")
    plt.ylabel("RPM")
    plt.grid(True, alpha=0.3)

    grafico_png = "grafico_rpm.png"
    plt.savefig(grafico_png, dpi=120, bbox_inches='tight')
    plt.close()

    # 2) CRIAR PDF
    arquivo = "relatorio.pdf"
    c = canvas.Canvas(arquivo)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 820, "Relatório da Sessão - Bancada de Testes")

    c.setFont("Helvetica", 12)
    c.drawString(50, 800, f"Total de registros: {len(hist)}")
    rpm_med = sum(rpms) / len(rpms) if rpms else 0
    temp_med = sum(temperaturas) / len(temperaturas) if temperaturas else 0
    c.drawString(50, 785, f"RPM médio: {rpm_med:.2f}")
    c.drawString(50, 770, f"Temperatura média: {temp_med:.2f} °C")

    # 3) GRÁFICO
    c.drawImage(grafico_png, 50, 520, width=500, height=220)

    # 4) ÚLTIMOS REGISTROS
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 500, "Últimos registros:")

    c.setFont("Helvetica", 9)
    y = 480
    for linha in hist[-20:]:
        text = (f"{linha['ts']}  |  RPM: {linha['rpm']:.2f}  |  "
                f"Temp: {linha['temperatura']:.2f} °C  |  "
                f"Tensão: {linha['tensao']:.2f} V  |  "
                f"Corrente: {linha['corrente']:.2f} A")
        c.drawString(50, y, text)
        y -= 12
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = 820

    c.save()

    if os.path.exists(grafico_png):
        os.remove(grafico_png)

    ui.download(arquivo)


# ==========================
# PÁGINAS
# ==========================
@ui.page('/')
def dashboard():
    aplicar_tema()
    menu()

    with ui.column().classes('p-6 gap-4'):
        ui.label('Dashboard — Monitoramento em tempo real') \
            .classes('text-2xl font-semibold text-gray-800')

        with ui.row().classes('gap-4 flex-wrap'):
            with ui.card().classes('p-4 rounded-xl shadow-sm bg-white min-w-[200px] flex-1'):
                ui.label('RPM').classes('text-xs uppercase text-gray-500')
                lbl_rpm = ui.label('0.00').classes('text-3xl font-bold text-gray-800')
                ui.label('Rotação do eixo').classes('text-xs text-gray-400')

            with ui.card().classes('p-4 rounded-xl shadow-sm bg-white min-w-[200px] flex-1'):
                ui.label('Temperatura (°C)').classes('text-xs uppercase text-gray-500')
                lbl_temp = ui.label('0.00').classes('text-3xl font-bold text-gray-800')
                ui.label('Sensor de temperatura').classes('text-xs text-gray-400')

            with ui.card().classes('p-4 rounded-xl shadow-sm bg-white min-w-[200px] flex-1'):
                ui.label('Tensão (V)').classes('text-xs uppercase text-gray-500')
                lbl_tensao = ui.label('0.00').classes('text-3xl font-bold text-gray-800')
                ui.label('Alimentação elétrica').classes('text-xs text-gray-400')

            with ui.card().classes('p-4 rounded-xl shadow-sm bg-white min-w-[200px] flex-1'):
                ui.label('Corrente (A)').classes('text-xs uppercase text-gray-500')
                lbl_corr = ui.label('0.00').classes('text-3xl font-bold text-gray-800')
                ui.label('Consumo de corrente').classes('text-xs text-gray-400')

        with ui.card().classes('mt-2 p-4 rounded-xl shadow-sm bg-white w-full'):
            ui.label('RPM em função do tempo').classes('text-sm font-semibold text-gray-700 mb-2')
            chart = ui.echart(
                {
                    'tooltip': {'trigger': 'axis'},
                    'xAxis': {'type': 'category', 'data': []},
                    'yAxis': {'type': 'value', 'name': 'RPM'},
                    'series': [{
                        'type': 'line',
                        'data': [],
                        'smooth': True,
                        'showSymbol': False,
                    }],
                    'grid': {'left': '8%', 'right': '4%', 'bottom': '8%', 'top': '8%'},
                }
            ).classes('w-full h-72')

        with ui.card().classes('mt-2 p-4 rounded-xl shadow-sm bg-white w-full'):
            ui.label('Última linha recebida da serial').classes('text-sm font-semibold text-gray-700 mb-1')
            lbl_ultima = ui.label('—').classes('text-xs text-gray-500 break-all')

        def atualizar():
            with lock:
                rpm = estado['rpm']
                temperatura = estado['temperatura']
                tensao = estado['tensao']
                corrente = estado['corrente']
                ultima = estado['ultima_linha']
                hist = estado['historico'][-50:]

            lbl_rpm.text = f'{rpm:.2f}'
            lbl_temp.text = f'{temperatura:.2f}'
            lbl_tensao.text = f'{tensao:.2f}'
            lbl_corr.text = f'{corrente:.2f}'
            lbl_ultima.text = ultima if ultima else '—'

            xs = [h['ts'].split(' ')[1] for h in hist]
            ys = [h['rpm'] for h in hist]

            chart.options['xAxis']['data'] = xs
            chart.options['series'][0]['data'] = ys
            chart.update()

        ui.timer(1, atualizar)


@ui.page('/calibracao')
def calibracao():
    aplicar_tema()
    menu()
    with ui.column().classes('p-6 gap-2'):
        ui.label("Calibração/Testes").classes("text-2xl font-semibold text-gray-800")
        ui.label("Área reservada para rotinas de calibração, acionamento de relés, testes manuais, etc.") \
            .classes("text-sm text-gray-500")


@ui.page('/relatorios')
def relatorios():
    aplicar_tema()
    menu()
    with ui.column().classes('p-6 gap-4'):
        ui.label("Relatórios").classes("text-2xl font-semibold text-gray-800")
        ui.label("Geração de relatórios em PDF e Excel com base nas medições capturadas.") \
            .classes("text-sm text-gray-500")

        with ui.card().classes("p-4 bg-white rounded-xl shadow-sm max-w-xl"):
            ui.label("Exportar dados").classes("text-sm font-semibold text-gray-700")
            ui.label("Selecione o formato desejado para exportar os dados da sessão atual.") \
                .classes("text-xs text-gray-500 mb-2")

            ui.button("📄 Baixar PDF", on_click=gerar_pdf).classes("mt-1 bg-primary text-white")
            ui.button("📊 Baixar Excel (XLSX)", on_click=gerar_excel).classes("mt-2 bg-white text-primary border border-primary")


@ui.page('/historico')
def historico():
    aplicar_tema()
    menu()
    with ui.column().classes('p-6 gap-4'):
        ui.label("Histórico de medições").classes("text-2xl font-semibold text-gray-800")

        with ui.card().classes('mt-2 p-4 bg-white rounded-xl shadow-sm w-full'):
            ui.label(f"Arquivo CSV atual: {ARQUIVO_CSV}").classes('text-xs text-gray-500 mb-2')

            tabela = ui.table({
                'columns': [
                    {'name': 'ts', 'label': 'Timestamp', 'field': 'ts'},
                    {'name': 'rpm', 'label': 'RPM', 'field': 'rpm'},
                    {'name': 'temperatura', 'label': 'Temp (°C)', 'field': 'temperatura'},
                    {'name': 'tensao', 'label': 'Tensão (V)', 'field': 'tensao'},
                    {'name': 'corrente', 'label': 'Corrente (A)', 'field': 'corrente'},
                ],
                'rows': [],
            }).classes('w-full')

            def atualizar():
                with lock:
                    tabela.options['rows'] = estado['historico'][-200:]
                    tabela.update()

            ui.timer(2, atualizar)


@ui.page('/configuracoes')
def config():
    aplicar_tema()
    menu()
    with ui.column().classes("p-6 gap-4"):
        ui.label("Configurações").classes("text-2xl font-semibold text-gray-800")

        with ui.card().classes("p-4 bg-white rounded-xl shadow-sm max-w-xl"):
            ui.label("Parâmetros de tolerância e ajuste").classes("text-sm font-semibold text-gray-700 mb-2")

            tol = ui.number("Tolerância RPM (%)", value=5.0).classes("w-full")
            k = ui.number("Fator K", value=1.0).classes("w-full mt-2")
            lim_temp = ui.number("Limite de Temperatura (°C)", value=80.0).classes("w-full mt-2")

            def salvar():
                ui.notify("Configurações salvas (apenas em memória nesta versão).", color='positive')

            ui.button("Salvar", on_click=salvar).classes("mt-3 bg-primary text-white")


@ui.page('/resumo')
def resumo():
    aplicar_tema()
    menu()
    with ui.column().classes("p-6 gap-4"):
        ui.label("Resumo da Sessão").classes("text-2xl font-semibold text-gray-800")

        with lock:
            hist = estado['historico'][:]

        total = len(hist)
        rpm_med = sum(h['rpm'] for h in hist) / total if total else 0
        temp_med = sum(h['temperatura'] for h in hist) / total if total else 0
        tensao_med = sum(h['tensao'] for h in hist) / total if total else 0
        corr_med = sum(h['corrente'] for h in hist) / total if total else 0

        with ui.card().classes("p-4 bg-white rounded-xl shadow-sm max-w-xl"):
            ui.label("Indicadores gerais").classes("text-sm font-semibold text-gray-700 mb-2")

            ui.label(f"Total de registros: {total}").classes("text-sm text-gray-600")
            ui.label(f"RPM médio: {rpm_med:.2f}").classes("text-sm text-gray-600")
            ui.label(f"Temperatura média: {temp_med:.2f} °C").classes("text-sm text-gray-600")
            ui.label(f"Tensão média: {tensao_med:.2f} V").classes("text-sm text-gray-600")
            ui.label(f"Corrente média: {corr_med:.2f} A").classes("text-sm text-gray-600")
            ui.label(f"CSV: {ARQUIVO_CSV}").classes("text-xs text-gray-400 mt-1")

            ui.separator().classes("my-3")

            ui.label("Exportar relatório completo:").classes("text-xs text-gray-500 mb-1")
            ui.button("📄 Baixar PDF", on_click=gerar_pdf).classes("mt-1 bg-primary text-white")
            ui.button("📊 Baixar Excel (XLSX)", on_click=gerar_excel).classes("mt-2 bg-white text-primary border border-primary")


@ui.page('/manutencao')
def manutencao():
    aplicar_tema()
    menu()
    with ui.column().classes("p-6 gap-2"):
        ui.label("Manutenção/Testes").classes("text-2xl font-semibold text-gray-800")
        ui.label("Página destinada a rotinas de manutenção preventiva, testes em hardware, logs detalhados, etc.") \
            .classes("text-sm text-gray-500")


@ui.page('/ajuda')
def ajuda():
    aplicar_tema()
    menu()
    with ui.column().classes("p-6 gap-2"):
        ui.label("Ajuda/Créditos").classes("text-2xl font-semibold text-gray-800")
        ui.markdown("""
**Projeto:** Supervisório da Bancada de Testes  
**Funções principais:** Aquisição via Serial, dashboard em tempo real, histórico, exportação em CSV/Excel/PDF.  

Desenvolvido em Python + NiceGUI.
        """).classes("text-sm text-gray-600")


# ==========================
# EXECUÇÃO
# ==========================
ui.run(title='Supervisório Bancada', reload=False)

rodando = False
t.join(timeout=1)

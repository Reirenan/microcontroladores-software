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
    'pulsos': 0,
    'rpm': 0.0,
    'ultima_linha': '',
    'historico': [],
}

lock = threading.Lock()

# ==========================
# LEITURA DA SERIAL
# ==========================
def parse_linha(linha: str):
    try:
        partes = linha.split('|')
        pulsos_txt = partes[0].strip()
        rpm_txt = partes[1].strip()

        pulsos = int(pulsos_txt.split(':')[1].strip())
        rpm = float(rpm_txt.split(':')[1].strip())
        return pulsos, rpm
    except Exception:
        return None, None


def thread_serial():
    global rodando
    try:
        with serial.Serial(PORTA_SERIAL, BAUDRATE, timeout=TIMEOUT) as ser:
            print(f'[SERIAL] Porta {PORTA_SERIAL} aberta.')

            try:
                with open(ARQUIVO_CSV, 'x', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'pulsos', 'rpm'])
            except FileExistsError:
                pass

            while rodando:
                linha = ser.readline().decode(errors='ignore').strip()
                if not linha:
                    continue

                pulsos, rpm = parse_linha(linha)
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with lock:
                    estado['ultima_linha'] = linha
                    if pulsos is not None:
                        estado['pulsos'] = pulsos
                        estado['rpm'] = rpm
                        estado['historico'].append({'ts': ts, 'pulsos': pulsos, 'rpm': rpm})

                if pulsos is not None:
                    with open(ARQUIVO_CSV, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([ts, pulsos, rpm])

    except serial.SerialException as e:
        print(f'[SERIAL] Erro: {e}')
    finally:
        print('[SERIAL] Thread finalizada.')


t = threading.Thread(target=thread_serial, daemon=True)
t.start()

# ==========================
# MENU SUPERIOR
# ==========================
def menu():
    with ui.header().classes('items-center justify-between'):
        ui.label('Supervisório - Bancada de Testes').classes('text-lg font-bold')

        with ui.row():
            ui.button('Dashboard', on_click=lambda: ui.navigate.to('/'))
            ui.button('Calibração/Testes', on_click=lambda: ui.navigate.to('/calibracao'))
            ui.button('Relatórios', on_click=lambda: ui.navigate.to('/relatorios'))
            ui.button('Histórico', on_click=lambda: ui.navigate.to('/historico'))
            ui.button('Configurações', on_click=lambda: ui.navigate.to('/configuracoes'))
            ui.button('Resumo da Sessão', on_click=lambda: ui.navigate.to('/resumo'))
            ui.button('Manutenção/Testes', on_click=lambda: ui.navigate.to('/manutencao'))
            ui.button('Ajuda/Créditos', on_click=lambda: ui.navigate.to('/ajuda'))


# ==========================
# PAGINAS
# ==========================

@ui.page('/')
def dashboard():
    menu()
    ui.label('Dashboard — Monitoramento em tempo real').classes('text-xl mt-4')

    with ui.row().classes('mt-4 gap-4'):
        card_p = ui.card().classes('p-4')
        with card_p:
            ui.label('Pulsos').classes('text-sm text-gray-500')
            lbl_p = ui.label('0').classes('text-3xl font-bold')

        card_r = ui.card().classes('p-4')
        with card_r:
            ui.label('RPM').classes('text-sm text-gray-500')
            lbl_r = ui.label('0.00').classes('text-3xl font-bold')

        card_u = ui.card().classes('p-4')
        with card_u:
            ui.label('Última linha').classes('text-sm text-gray-500')
            lbl_u = ui.label('—').classes('text-md')

    with ui.card().classes('mt-4 w-full'):
        ui.label('RPM em função do tempo').classes('text-sm')
        chart = ui.echart(
            {
                'xAxis': {'type': 'category', 'data': []},
                'yAxis': {'type': 'value'},
                'series': [{'type': 'line', 'data': []}],
            }
        ).classes('w-full h-64')

    def atualizar():
        with lock:
            pulsos = estado['pulsos']
            rpm = estado['rpm']
            ultima = estado['ultima_linha']
            hist = estado['historico'][-50:]

        lbl_p.text = pulsos
        lbl_r.text = f'{rpm:.2f}'
        lbl_u.text = ultima

        xs = [h['ts'].split(' ')[1] for h in hist]
        ys = [h['rpm'] for h in hist]

        chart.options['xAxis']['data'] = xs
        chart.options['series'][0]['data'] = ys
        chart.update()

    ui.timer(1, atualizar)


@ui.page('/calibracao')
def calibracao():
    menu()
    ui.label("Calibração/Testes").classes("text-xl mt-4")
    ui.label("Botões, relés, comandos e testes serão colocados aqui.").classes("mt-2")


@ui.page('/relatorios')
def relatorios():
    menu()
    ui.label("Relatórios").classes("text-xl mt-4")
    ui.label("Aprovado/Reprovado baseado nas tolerâncias.").classes("mt-2")


@ui.page('/historico')
def historico():
    menu()
    ui.label("Histórico de medições").classes("text-xl mt-4")

    with ui.card().classes('mt-4'):
        ui.label(f"Arquivo CSV: {ARQUIVO_CSV}").classes('text-sm text-gray-500')

        tabela = ui.table({
            'columns': [
                {'name': 'ts', 'label': 'Timestamp', 'field': 'ts'},
                {'name': 'pulsos', 'label': 'Pulsos', 'field': 'pulsos'},
                {'name': 'rpm', 'label': 'RPM', 'field': 'rpm'},
            ],
            'rows': [],
        })

        def atualizar():
            with lock:
                tabela.options['rows'] = estado['historico'][-100:]
                tabela.update()

        ui.timer(2, atualizar)


@ui.page('/configuracoes')
def config():
    menu()
    ui.label("Configurações").classes("text-xl mt-4")

    with ui.card().classes("mt-4 w-full max-w-xl"):
        ui.label("Tolerâncias").classes("text-sm")
        tol = ui.number("Tolerância RPM (%)", value=5.0)
        k = ui.number("Fator K", value=1.0)
        lim = ui.number("Limite Pulsos", value=100)

        ui.button("Salvar", on_click=lambda: ui.notify("Configurações salvas")).classes("mt-2")

def gerar_excel():
    with lock:
        hist = estado['historico'][:]

    if not hist:
        return ui.notify("Sem dados para exportar!")

    df = pd.DataFrame(hist)
    arquivo = "relatorio.xlsx"
    df.to_excel(arquivo, index=False)

    ui.download(arquivo)


def gerar_pdf():
    with lock:
        hist = estado['historico'][:]

    if not hist:
        return ui.notify("Sem dados para exportar!")

    # =======================
    # 1) GERAR GRÁFICO PNG
    # =======================
    tempos = [h['ts'] for h in hist]
    rpms   = [h['rpm'] for h in hist]

    plt.figure(figsize=(10,4))
    plt.plot(rpms, linewidth=2)
    plt.title("RPM ao longo da sessão")
    plt.xlabel("Amostra")
    plt.ylabel("RPM")
    plt.grid(True)

    grafico_png = "grafico_rpm.png"
    plt.savefig(grafico_png, dpi=120, bbox_inches='tight')
    plt.close()

    # =======================
    # 2) CRIAR O PDF
    # =======================
    arquivo = "relatorio.pdf"
    c = canvas.Canvas(arquivo)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 820, "Relatório da Sessão - Bancada de Testes")

    c.setFont("Helvetica", 12)
    c.drawString(50, 800, f"Total de registros: {len(hist)}")
    rpm_med = sum(rpms)/len(rpms) if rpms else 0
    c.drawString(50, 785, f"RPM médio: {rpm_med:.2f}")

    # =======================
    # 3) INSERIR O GRÁFICO
    # =======================
    c.drawImage(grafico_png, 50, 500, width=500, height=250)

    # =======================
    # 4) INSERIR ÚLTIMOS REGISTROS
    # =======================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 470, "Últimos registros:")

    c.setFont("Helvetica", 10)
    y = 450
    for linha in hist[-20:]:  # últimas 20 linhas
        text = f"{linha['ts']}  |  Pulsos: {linha['pulsos']}  |  RPM: {linha['rpm']:.2f}"
        c.drawString(50, y, text)
        y -= 14
        if y < 40:   # quebra de página
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 820

    c.save()

    # remover PNG temporário
    if os.path.exists(grafico_png):
        os.remove(grafico_png)

    # baixar o PDF
    ui.download(arquivo)


@ui.page('/resumo')
def resumo():
    menu()
    ui.label("Resumo da Sessão").classes("text-xl mt-4")

    with lock:
        hist = estado['historico'][:]

    total = len(hist)
    rpm_med = sum(h['rpm'] for h in hist) / total if total else 0

    with ui.card().classes("mt-4 w-full max-w-xl"):
        ui.label(f"Total registros: {total}")
        ui.label(f"RPM médio: {rpm_med:.2f}")
        ui.label(f"CSV: {ARQUIVO_CSV}")

        ui.separator()

        ui.label("Exportar relatório:")

        ui.button("📄 Baixar PDF", on_click=gerar_pdf).classes("mt-2")
        ui.button("📊 Baixar Excel (XLSX)", on_click=gerar_excel).classes("mt-2")



@ui.page('/manutencao')
def manutencao():
    menu()
    ui.label("Manutenção/Testes").classes("text-xl mt-4")


@ui.page('/ajuda')
def ajuda():
    menu()
    ui.label("Ajuda/Créditos").classes("text-xl mt-4")
    ui.markdown("""
    **Projeto:** Supervisório  
    **Funções:** Serial, supervisório, CSV, relatórios  
    """)

# ==========================
# EXECUÇÃO
# ==========================
ui.run(title='Supervisório Bancada', reload=False)

rodando = False
t.join(timeout=1)

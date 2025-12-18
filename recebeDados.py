import serial

# ===============================
# CONFIGURAÇÃO SERIAL
# ===============================
porta_serial = 'COM2'
taxa_baude = 115200

# ===============================
# MAIN – SOMENTE LEITURA
# ===============================
try:
    with serial.Serial(porta_serial, taxa_baude, timeout=1) as ser:
        print("Aguardando dados da serial... (Ctrl+C para sair)\n")

        while True:
            linha = ser.readline().decode('utf-8', errors='ignore').strip()
            if linha:
                print(f"[RX] {linha}")

except serial.SerialException as e:
    print(f"Erro na serial: {e}")

except KeyboardInterrupt:
    print("\nLeitura interrompida pelo usuário.")

print("Programa finalizado.")

import serial
import time

# Configurações da porta serial
porta_serial = 'COM2'
taxa_baude = 9600

try:
    with serial.Serial(porta_serial, taxa_baude, timeout=1) as ser:
        print("Serial conectada. Digite comandos (ex: l13, d13).")
        print("Digite 'sair' para encerrar.\n")

        while True:
            comando = input(">> ").strip()

            if comando.lower() == 'sair':
                break

            ser.write((comando + '\n').encode())
            ser.flush()

            print(f"[TX] {comando}")

except serial.SerialException as e:
    print(f"Erro ao acessar a porta serial: {e}")

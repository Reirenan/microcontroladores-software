import time
import serial

# configure the serial connections
ser = serial.Serial(
    port='COM5',
    baudrate=9600,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_TWO,
    bytesize=serial.SEVENBITS
)

ser.isOpen()

print('Enter your commands below.\r\nInsert "exit" to leave the application.')

while True:
    cmd = input(">> ")

    if cmd == 'exit':
        ser.close()
        exit()
    else:
        # enviar como bytes
        ser.write((cmd + '\r\n').encode())

        time.sleep(1)

        out = b""
        while ser.inWaiting() > 0:
            out += ser.read(1)

        if out != b"":
            print(">> " + out.decode(errors="ignore"))

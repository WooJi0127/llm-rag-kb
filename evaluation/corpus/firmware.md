STM32 firmware reads sensors through I2C and reports measurements through UART. 固件负责定时采集、串口上报和看门狗。FreeRTOS schedules separate tasks.

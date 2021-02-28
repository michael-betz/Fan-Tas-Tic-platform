'''Fantastic serial communicator.'''
from mpf.platforms.base_serial_communicator import BaseSerialCommunicator


class FanTasTicSerialCommunicator(BaseSerialCommunicator):
    # from https://docs.google.com/spreadsheets/d/1QlxT6QhTLHodxV4uOGEEIK3jQQLPyiI4lmSObMyx4UE/edit?usp=sharing
    errStrs = {
        0x0000: "I2CMCommand() not added to queue",
        0x0001: "I2C PCFL communication error",
        0x0003: "No PCFLs discovered!",
        0x0004: "Error, no more space in g_outWriterList :(",
        0x0005: "WTF! unknow SPI DMA state.",
        0x0006: "[CMDLINE_BAD_CMD]",
        0x0007: "[CMDLINE_INVALID_ARG]",
        0x0008: "[CMDLINE_TOO_FEW_ARGS]",
        0x0009: "[CMDLINE_TOO_MANY_ARGS]",
        0x000A: "taskUsbCommandParser(), Command buffer overflow, try a shorter command!",
        0x000B: "Unknown currentMode!, taskUsbCommandParser()",
        0x000C: "Cmd_SW(): string buffer overflow!",
        0x000D: "inputSwitchId invalid, Cmd_DEB()",
        0x000E: "Cmd_OUT(): I2C PWMvalue must be < , (1 << N_BIT_PWM)",
        0x000F: "Cmd_OUT(): HW PWMvalue must be <= , MAX_PWM",
        0x0010: "Cmd_OUT(): HW_INDEX_INVALID: , argv[1]",
        0x0011: "Cmd_OUT(): HW_INDEX_INVALID: , argv[1]",
        0x0012: "unknown hwIndex type (fatal)",
        0x0013: "quickRuleId must be < , Cmd_RULE(),",
        0x0014: "quickRuleId must be < , Cmd_RUL(),",
        0x0015: "inputSwitchId invalid, Cmd_RUL(), argv[2] ",
        0x0016: "pwmValues must be < , Cmd_RUL(), (1 << N_BIT_PWM) ",
        0x0017: "HW pwmValues must be < , Cmd_RUL(), MAX_PWM ",
        0x0018: "outputDriverId invalid, Cmd_RUL(), argv[3] ",
        0x0019: "Invalid LED channel (), Cmd_LEC(), channel",
        0x001A: "Invalid number of bytes (), Cmd_LED(), blobSize",
        0x001B: "Timeout, could not access sendBuffer , spiSend(), channel",
        0x001C: "Invalid LED channel (), Cmd_LED(), channel",
        0x001D: "Invalid number of arguments (), Cmd_LED(), argc",
        0x001E: "I2C Channel must be <= 4, Cmd_I2C()",
        0x001F: "Too many bytes to receive: , max. , Cmd_I2C(), g_customI2CnBytesRx, CUSTOM_I2C_BUF_LEN",
        0x0020: "Too many bytes to send: , max. , Cmd_I2C(), nBytesTx, CUSTOM_I2C_BUF_LEN",
        0x0021: "handle_i2c_custom(): Error! I2C not in IDLE state",
        0x0022: "handle_i2c_custom(): Could not allocate hexStr buffer!",
        0x0023: "setup_pcf_rw(): busy error",
        0x0024: "stupid_i2c_send(): timeout on ch ! SDA pullups installed?, _get_ch(b)",
        0x0025: "i2cUnstucker()        : pin stuck low @: , base",
        0x0100: "I2C write error count exceeded",
        0x0101: "Watchdog timer expired"
    }

    def __init__(self, platform, port: str, serialCommandCallbacks=dict()):
        '''
            serialCommandCallbacks
                dict(), key is command type (b'ID') value is a
                callback function `receive_id( msg )`
        '''
        # baudrate is ignored by hardware
        super().__init__(platform, port, 115200)
        self._rxBuffer = bytearray()
        self._serialCommands = {
            b'ID': self._receive_id,  # Received a processor ID and version
            b'ER': self._receive_er   # Received an error code
        }
        self._serialCommands.update(serialCommandCallbacks)

    async def _identify_connection(self):
        '''Initialise and identify connection.'''
        self.send(b'\n\n\n\n\n')
        self.send(b'*IDN?\n')  # Get version and ID
        vString = await self.readuntil(b'\n')
        if not vString.startswith(b'ID:MB:'):
            self.log.error(
                'Could not connect to FanTasTic PCB, wrong response:',
                vString
            )
            self.machine.stop('Fan-Tas-Tic communication error')
        self.log.info(
            'Connected to Fan-Tas-Tic: %s ',
            vString.decode().strip()
        )
        await self.start_read_loop()

    def send(self, msg):
        '''Send a message to the remote processor over the serial connection.

        Args:
            msg: Bytes or str of the message you want to send.
        '''
        if type(msg) is str:
            msg = bytes(msg, 'utf8')
        super().send(msg)

    def _addToRxBuffer(self, msg, sep='\n'):
        '''
        adds msg data to rx buffer until sep is found,
        then returns a complete message, (without sep).

        If sep is not found, it returns b''
        '''
        self._rxBuffer.extend(msg)
        while True:
            fullBuff, part, remaindBuff = self._rxBuffer.partition(b'\n')
            if part != b'\n':   # Found not even one complete message
                break
            self._rxBuffer = remaindBuff
            yield fullBuff

    def _parse_msg(self, msg):
        '''Parse a message.
        Sends an incoming message from the fantastic controller to the proper
        method for servicing.
        Msg may be partial.
        Args:
            msg: Bytes of the message (part) received.
        '''
        # Take care of buffering partials and returns only complete messages
        for completeMsg in self._addToRxBuffer(msg):
            if completeMsg[2:3] != b':':
                self.send(b'\n')   # Clear previous commands
                self._rxBuffer.clear()
                self.log.error(
                    'Serial communicator : Received malformed message: %s',
                    completeMsg
                )
                return
            cmd = bytes(completeMsg[0:2])
            payload = completeMsg[3:]
            # Can't use try since it swallows too many errors for now
            if cmd in self._serialCommands:
                self._serialCommands[cmd](payload)
            else:
                self.log.error(
                    'Received unknown serial command? %s',
                    completeMsg
                )

    def _receive_id(self, payload):
        ''' Parses the ID payload. Not really used, more of a demonstration '''
        self.log.info(
            'Received Fan-Tas-Tic firmware version: %s',
            payload.decode()
        )

    def _receive_er(self, payload):
        ''' Recived an error code like ER:xxxx\n '''
        errCode = int(payload)

        errStr = FanTasTicSerialCommunicator.errStrs.get(errCode, "")
        errStr = 'FanTasTic Hardware Error: 0x%04X. {:}'.format(
            errCode, errStr
        )

        if (errCode >= 0x0100):
            errStr += ' Fatal! Shutting down!'
            self.log.error(errStr)
            self.machine.stop(errStr)
        else:
            self.log.error(errStr)

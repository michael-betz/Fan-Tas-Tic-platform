"""Fantastic serial communicator."""
import asyncio, logging
from mpf.platforms.base_serial_communicator import BaseSerialCommunicator

class FanTasTicSerialCommunicator(BaseSerialCommunicator):

    def __init__(self, platform, port: str, serialCommandCallbacks=dict() ):
        """
            serialCommandCallbacks
                dict(), key is command type (b"ID") value is a
                callback function `receive_id( msg )`
        """
        super().__init__( platform, port, 115200 )  #Note the baudrate is fake
        self.log = logging.getLogger("FanTasTicSerialCommunicator")
        self._rxBuffer = bytearray()
        self._serialCommands = {
            b'ID' : self._receive_id, # Received a processor ID and version
            b'ER' : self._receive_er  # Received an error code
        }
        self._serialCommands.update( serialCommandCallbacks )

    @asyncio.coroutine
    def _identify_connection(self):
        """Initialise and identify connection."""
        self.send(b"\n\n\n\n\n")
        self.send(b"*IDN?\n") #Get version and ID
        vString = yield from self.readuntil( b"\n" )
        if not vString.startswith(b"ID:MB:"):
            raise RuntimeError("Could not connect to FanTasTic PCB, wrong response:", vString)
        self.log.info("Connected to Fan-Tas-Tic: %s ", vString.decode().strip() )
        yield from self.start_read_loop()

    def send(self, msg):
        """Send a message to the remote processor over the serial connection.

        Args:
            msg: Bytes or str of the message you want to send.
        """
        if type(msg) is str:
            msg = bytes(msg, "utf8")
        super().send( msg )

    def _addToRxBuffer( self, msg, sep="\n" ):
        ''' adds msg data to rx buffer until sep is found, then returns a complete message,
        (without sep). If sep is not found, it returns b"" '''
        self._rxBuffer.extend( msg )
        while True:
            fullBuff, part, remaindBuff = self._rxBuffer.partition(b"\n")
            if part != b"\n":   #Found not even one complete message
                break
            self._rxBuffer = remaindBuff
            yield fullBuff

    def _parse_msg(self, msg):
        """Parse a message.
        Sends an incoming message from the fantastic controller to the proper
        method for servicing.
        Msg may be partial.
        Args:
            msg: Bytes of the message (part) received.
        """
        # Take care of buffering partials and returns only complete messages
        for completeMsg in self._addToRxBuffer( msg ):
            if completeMsg[2:3] != b':':
                self.send(b"\n")   # Clear previous commands
                self._rxBuffer.clear()
                self.log.error("Received malformed message: %s", completeMsg)
                return
            cmd = bytes(completeMsg[0:2])
            payload = completeMsg[3:]
            # Can't use try since it swallows too many errors for now
            if cmd in self._serialCommands:
                self._serialCommands[cmd](payload)
            else:
                self.log.error("Received unknown serial command? %s", completeMsg)

    def _receive_id( self, payload ):
        """ Parses the ID payload. Not really used, more of a demonstration """
        self.log.info("Received Fan-Tas-Tic firmware version: %s", payload.decode() )

    def _receive_er( self, payload ):
        """ Recived an error code like ER:xxxx\n """
        errCode = int(payload)
        self.log.error("FanTasTic Hardware Error: 0x%02X\nI'm lazy, look it up here https://docs.google.com/spreadsheets/d/1QlxT6QhTLHodxV4uOGEEIK3jQQLPyiI4lmSObMyx4UE/edit?usp=sharing", errCode )

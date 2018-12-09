from asyncio import AbstractEventLoop
from mpf.platforms.interfaces.light_platform_interface import LightPlatformSoftwareFade

class FanTasTicLight( LightPlatformSoftwareFade ):
    __slots__ = ["arrs", "inds"]

    def __init__(self, loop: AbstractEventLoop, software_fade_ms: int, number: str, ledByteArrayRefs: list ) -> None:
        """
            ledByteArrayRef:
                reference to the raw bytesarray with all LED data. This is indexed and written to

            targetIndex:
                where to write the brightness to
        """
        super().__init__(number, loop, software_fade_ms)

        # number = "<colorIndex>, 1-38, 1-39"
        ns = number.split(",")
        colorIndex = int( ns.pop(0).strip() )
        # ns = [' 1-38', ' 1-39']
        self.arrs = list()
        self.inds = list()
        for n in ns:
            #----------------------------------------------
            # Find the right led-byte-array and index
            #----------------------------------------------
            ledChannel, ledNumber = n.strip().split("-")
            ledByteArrayRef = ledByteArrayRefs[ int(ledChannel) ]
            targetIndex = int(ledNumber)*3 + colorIndex
            #----------------------------------------------
            # Check if LED byte array needs to be extended
            #----------------------------------------------
            if targetIndex >= len( ledByteArrayRef ): # index does not exist, we need to extend the array
                ledByteArrayRef += b"\x00"*( (targetIndex+1)-len(ledByteArrayRef) )
            self.arrs.append( ledByteArrayRef )    # This is hopefully by reference
            self.inds.append( targetIndex )

    def set_brightness(self, brightness: float):
        """Set the light to the specified brightness.

        Args:
            brightness: float of the brightness

        Returns:
            None
        """
        for arr, ind in zip(self.arrs, self.inds):
            arr[ ind ] = int( brightness * 255 )

    def get_board_name(self):
        """Return the name of the board of this driver."""
        return "FanTasTic-board"


import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb.utils import get_sim_time
from cocotb.binary import BinaryValue
from cocotb_bus.bus import Bus

class MemoryRegion:
    def __init__(self, size):
        self.size = size
        self.memory = bytearray(size)

    def read(self, address, length):
        return bytes(self.memory[address:address+length])

    def write(self, address, data, length):
        self.memory[address:address+length] = data

class DQDriver:
    def __init__(self, dut):
        self.dut = dut

    async def drive(self, value):
        if isinstance(value, str):
            value = BinaryValue(value, 8)
        elif not isinstance(value, BinaryValue):
            value = BinaryValue(value, 8)
        
        for i in range(8):
            self.dut.__getattr__(f'dq{i}').value = value[i]
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

    async def drive_high_impedance(self):
        for i in range(8):
            self.dut.__getattr__(f'dq{i}').value = BinaryValue('Z')
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class RWDSDriver:
    def __init__(self, dut):
        self.dut = dut

    async def drive(self, value):
        self.dut.rwds.value = value
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

    async def drive_high_impedance(self):
        self.dut.rwds.value = BinaryValue('Z')
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class CS_Driver:
    def __init__(self, dut):
        self.dut = dut

    async def drive(self, value):
        self.dut.csneg.value = value
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class HyperBusMemory(Bus):
    _signals = ['ck','cs_n','rwds_in','rwds_out','dq_in','dq_out']

    def __init__(self, dut, clk, rst, address_width=32, data_width=32, initial_latency=4, fixed_latency=True, burst_length=32):
        super().__init__(dut,name, self._signals)
        self.dut = dut
        self.clk = clk
        self.rst = rst
        self.address_width = address_width
        self.data_width = data_width
        self.memory = MemoryRegion(2**address_width)  # Initialize memory region
        self.initial_latency = initial_latency
        self.fixed_latency = fixed_latency
        self.burst_length = burst_length
        self.ca_bytes = []

        # Initialize signals
        self.bus.cs_n.value = 1
        self.bus.rwds_in.value = 1
        self.bus.dq_in.value = 0

        # Initialize drivers
        self.dq_driver = DQDriver(dut)
        self.rwds_driver = RWDSDriver(dut)
        self.cs_driver = CS_Driver(dut)

        # Start the clock
        cocotb.start_soon(Clock(self.clk, 10, units='ns').start())

        # Reset the interface
        cocotb.start_soon(self.reset())

    async def reset(self):
        self.rst.value = 1  # Initial state of reset signal
        await Timer(100, 'ns')
        self.rst.value = 0  # Assert reset
        await Timer(100, 'ns')
        self.rst.value = 1  # Deassert reset
        await Timer(100, 'ns')  # Wait for some time after deasserting reset

    async def read(self, address):
        # Simulate a read operation with initial latency
        await Timer(self.initial_latency * 10, 'ns')  # Initial latency in clock cycles
        data = self.memory.read(address, self.data_width // 8)
        return data

    async def write(self, address, data):
        # Simulate a write operation with initial latency
        await Timer(self.initial_latency * 10, 'ns')  # Initial latency in clock cycles
        self.memory.write(address, data, self.data_width // 8)

    def decode_address(self, dq_value):
        """
        Decode the DQ bus value into a memory address based on the HyperBus specification.
        """
        # Extract bits from the DQ bus value
        r_w = (dq_value >> 47) & 0x1  # Read/Write bit
        as_ = (dq_value >> 46) & 0x1  # Address Space bit
        burst_type = (dq_value >> 45) & 0x1  # Burst Type bit
        row_column = (dq_value >> 2) & 0x3  # Row & Upper Column bits
        lower_column = dq_value & 0x3  # Lower Column bits

        # Construct the memory address (simplified example)
        memory_address = (row_column << 5) | lower_column  # Combine row and column parts
        return memory_address, r_w, addr_space

    async def handle_transactions(self):
    """
    Handles a memory transaction by capturing Command/Address (CA) bits.

    - Captures CA bits on both rising and falling edges of CK.
    - Starts capturing only when `CS#` goes low (indicating a valid transaction).
    - Captures 6 bytes (48 bits) of CA over 3 clock cycles.
    - If `CS#` is deasserted (goes high) before all 6 bytes are captured,  
      the transaction is aborted and the CA buffer is reset.
    - Once a full CA sequence is captured, it is decoded to determine  
      if the transaction is a read or write.
    - If read, the corresponding data is driven onto the bus.  
      If write, the received data is stored in memory.
    - The function waits for CS# to go high before allowing a new transaction.
    """

    	
	    while True:
		await FallingEdge(self.bus.cs_n)  # Wait for CS# to go LOW (start of transaction)
		self.transaction_active = True  # Transaction is active
		self.ca_bytes = []  # Reset CA buffer

		for _ in range(3):  # 3 clock cycles → 6 CA bytes
		    await RisingEdge(self.bus.ck)  # Capture on rising edge
		    if self.bus.cs_n.value == 1:  # If CS# goes high, abort transaction
		        self.transaction_active = False
		        self.ca_bytes = []
		        break
		    self.capture_ca()

		    await FallingEdge(self.bus.ck)  # Capture on falling edge
		    if self.bus.cs_n.value == 1:  # If CS# goes high, abort transaction
		        self.transaction_active = False
		        self.ca_bytes = []
		        break
		    self.capture_ca()

		if len(self.ca_bytes) == 6:  # Ensure full capture before decoding
		    address, rw, addr_space = self.decode_address()
		    self.ca_bytes = []  # Reset CA buffer

		    if rw:  # Read transaction
		        data = await self.read(address)
		        await self.dq_driver.drive(data)  # Drive data to the bus
		    else:  # Write transaction
		        await RisingEdge(self.bus.ck)  # Ensure proper timing
		        data_in = int(self.bus.dq_in.value)
		        await self.write(address, data_in)  # Write data

		await RisingEdge(self.bus.cs_n)  # Wait for CS# to go HIGH (transaction end)
		self.transaction_active = False  # Mark transaction as inactive

    def capture_ca(self):
	    """
	    Captures the CA bits from the bus.
	    """
	    ca_byte = int(self.bus.dq_in.value)
	    self.ca_bytes.append(ca_byte)

    def log(self, msg):
        print(f'[{get_sim_time("ns")}]  {msg}')

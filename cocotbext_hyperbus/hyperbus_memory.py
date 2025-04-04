import cocotb
from cocotb.triggers import Timer, RisingEdge, FallingEdge
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

class ConfigurationRegister:
    def __init__(self):
        self.deep_power_down = 0
        self.output_drive_strength = 0
        self.initial_latency = 4
        self.fixed_latency = True
        self.burst_length = 32
        self.hybrid_wrap = False

    def set_register(self, register_value):
        self.deep_power_down = (register_value >> 15) & 0x1
        self.output_drive_strength = (register_value >> 12) & 0x7
        self.initial_latency = (register_value >> 4) & 0xF
        self.fixed_latency = (register_value >> 3) & 0x1
        self.burst_length = (register_value >> 1) & 0x3
        self.hybrid_wrap = register_value & 0x1

class HyperBusMemory(Bus):
    _signals = ['ck', 'o_csn0', 'o_dq', 'i_dq', 'o_rwds', 'i_rwds']

    def __init__(self, dut, clk, rst, address_width=32, data_width=32, initial_latency=4, fixed_latency=True, burst_length=32):
        super().__init__(dut, "hyperbus", self._signals)
        self.dut = dut
        self.clk = clk
        self.rst = rst
        self.bus = dut
        self.address_width = address_width
        self.data_width = data_width
        self.memory = MemoryRegion(2**address_width)  # Initialize memory region
        self.initial_latency = initial_latency
        self.fixed_latency = fixed_latency
        self.burst_length = burst_length
        self.ca_bytes = []
        self.config_register = ConfigurationRegister()

        # Initialize signals
        self.bus.o_csn0.value = 1
        self.bus.i_rwds.value = 1
        self.bus.i_dq.value = 0

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
        r_w = (dq_value >> 47) & 0x1  # Read/Write bit
        as_ = (dq_value >> 46) & 0x1  # Address Space bit
        burst_type = (dq_value >> 45) & 0x1  # Burst Type bit
        row_column = (dq_value >> 16) & 0xFFFF  # Row & Upper Column bits
        lower_column = dq_value & 0xFF  # Lower Column bits
        address = (row_column << 8) | lower_column  # Combine row and column parts
        return address, r_w, as_, burst_type

    def handle_burst(self, address, length, burst_type):
        data = bytearray()
        group_size = self.burst_length  # Assuming burst_length is the group size

        if burst_type == 'wrapped':
            # Implement wrapped burst logic
            for i in range(length):
                effective_address = (address + i) % group_size
                data.append(self.memory.read(effective_address, 1))
        elif burst_type == 'linear':
            # Implement linear burst logic
            data = self.memory.read(address, length)
        elif burst_type == 'hybrid':
            # Implement hybrid burst logic
            wrapped_length = group_size - (address % group_size)
            if wrapped_length > length:
                wrapped_length = length
            data = self.handle_burst(address, wrapped_length, 'wrapped')
            if length > wrapped_length:
                linear_length = length - wrapped_length
                linear_address = address + wrapped_length
                data += self.handle_burst(linear_address, linear_length, 'linear')
        return data

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
            await FallingEdge(self.bus.o_csn0)  # Wait for CS# to go LOW (start of transaction)
            self.transaction_active = True  # Transaction is active
            self.ca_bytes = []  # Reset CA buffer

            for _ in range(3):  # 3 clock cycles → 6 CA bytes
                await RisingEdge(self.bus.ck)  # Capture on rising edge
                if self.bus.o_csn0.value == 1:  # If CS# goes high, abort transaction
                    self.transaction_active = False
                    self.ca_bytes = []
                    break
                self.capture_ca()

                await FallingEdge(self.bus.ck)  # Capture on falling edge
                if self.bus.o_csn0.value == 1:  # If CS# goes high, abort transaction
                    self.transaction_active = False
                    self.ca_bytes = []
                    break
                self.capture_ca()

            if len(self.ca_bytes) == 6:  # Ensure full capture before decoding
                ca_value = int.from_bytes(self.ca_bytes, byteorder="big")
                address, rw, addr_space, burst_type = self.decode_address(ca_value)
                self.ca_bytes = []  # Reset CA buffer
                # Check RWDS during CA phase for additional latency
                additional_latency = 0
                if self.bus.rwds.value == 1:    # RWDS high indicates additional latency
                    additional_latency = self.initial_latency  # Insert additional latency period
                    
                if rw:  # Read transaction
                    if burst_type == 0:  # Wrapped burst
                    	data = self.handle_burst(address, self.burst_length, 'wrapped')
                    elif burst_type == 1:  # Linear burst
                    	data = self.handle_burst(address, self.burst_length, 'linear')
                    await self.dq_driver.drive(data)  # Drive data to the bus
                else:  # Write transaction
                    await RisingEdge(self.bus.ck)  # Ensure proper timing
                    data_in = int(self.bus.i_dq.value)
                    mask = int(self.bus.i_rwds.value)
                    await self.write_with_masking(address, data_in, mask)

            await RisingEdge(self.bus.o_csn0)  # Wait for CS# to go HIGH (transaction end)
            self.transaction_active = False  # Mark transaction as inactive

    def capture_ca(self):
        ca_byte = int(self.bus.i_dq.value)
        self.ca_bytes.append(ca_byte)

    async def write_with_masking(self, address, data, mask):
        for i in range(len(data)):
            if mask[i] == 0:  # Mask bit is 0, write the byte
                self.memory.write(address + i, data[i], 1)

    async def enter_deep_power_down(self):
        self.config_register.deep_power_down = 1
        # Implement power-down logic

    async def exit_deep_power_down(self):
        self.config_register.deep_power_down = 0
        # Implement power-up logic

    def handle_error(self):
        self.rwds_driver.drive_high_impedance()
        Timer(32, 'ns')  # Hold RWDS Low for 32 clock cycles

    def log(self, msg):
        print(f'[{get_sim_time("ns")}]  {msg}')

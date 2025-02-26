import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotb.handle import Release, Freeze, Force
from cocotb.utils import get_sim_time
from cocotb.binary import BinaryValue

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

class HyperBusMemory:
    def __init__(self, dut, clk, rst, address_width=32, data_width=32, initial_latency=4, fixed_latency=True, burst_length=32):
        self.dut = dut
        self.clk = clk
        self.rst = rst
        self.address_width = address_width
        self.data_width = data_width
        self.memory = {}
        self.initial_latency = initial_latency
        self.fixed_latency = fixed_latency
        self.burst_length = burst_length

        # Initialize signals
        self.dut.csneg.value = 1
        self.dut.RWDS.value = 1
        self.dut.DQ.value = 0

        # Initialize drivers
        self.dq_driver = DQDriver(dut)
        self.rwds_driver = RWDSDriver(dut)
        self.cs_driver = CS_Driver(dut)

        # Start the clock
        cocotb.start_soon(Clock(self.clk, 10, units='ns').start())

        # Reset the interface
        cocotb.start_soon(self.reset())

        # Define the target memory region
        self.target = MemoryRegion(2**self.address_width)

    async def reset(self):
        self.rst.value = 0
        await Timer(100, 'ns')
        self.rst.value = 1
        await Timer(100, 'ns')

    async def read(self, address):
        # Simulate a read operation with initial latency
        await Timer(self.initial_latency * 10, 'ns')  # Initial latency in clock cycles
        data = self.target.read(address, self.data_width // 8)
        return data

    async def write(self, address, data):
        # Simulate a write operation with initial latency
        await Timer(self.initial_latency * 10, 'ns')  # Initial latency in clock cycles
        self.target.write(address, data, self.data_width // 8)

    async def handle_transactions(self):
        while True:
            await RisingEdge(self.clk)
            if self.dut.CS_.value == 0:  # Transaction active
                if self.dut.RWDS.value == 0:  # Write transaction
                    address = int(self.dut.DQ.value)  # Simplified address extraction
                    data = int(self.dut.DQ.value)  # Simplified data extraction
                    await self.write(address, data)
                else:  # Read transaction
                    address = int(self.dut.DQ.value)  # Simplified address extraction
                    data = await self.read(address)
                    await self.dq_driver.drive(data)  # Drive data back to the bus

    def log(self, msg):
        print(f'[{get_sim_time("ns")}]  {msg}')

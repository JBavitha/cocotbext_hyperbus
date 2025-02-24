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
        self.dut.DQ.value = value
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

    async def drive_high_impedance(self):
        self.dut.DQ.value = BinaryValue('Z')
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class RWDSDriver:
    def __init__(self, dut):
        self.dut = dut

    async def drive(self, value):
        self.dut.RWDS.value = value
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

    async def drive_high_impedance(self):
        self.dut.RWDS.value = BinaryValue('Z')
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class CS_Driver:
    def __init__(self, dut):
        self.dut = dut

    async def drive(self, value):
        self.dut.CS_.value = value
        await Timer(1, 'ns')  # Small delay to ensure the value is driven

class HyperBusMemory:
    def __init__(self, dut, clk, rst, target, address_width=32, data_width=32, initial_latency=4, fixed_latency=True, burst_length=32, clk_period=10):
        self.dut = dut
        self.clk = clk
        self.rst = rst
        self.target = target  # Target memory region as input
        self.address_width = address_width
        self.data_width = data_width
        self.memory = {}
        self.initial_latency = initial_latency
        self.fixed_latency = fixed_latency
        self.burst_length = burst_length
        self.clk_period = clk_period  # Clock period in ns

        # Initialize signals
        self.dut.CS_.value = 1
        self.dut.RWDS.value = 1
        self.dut.DQ.value = 0

        # Initialize drivers
        self.dq_driver = DQDriver(dut)
        self.rwds_driver = RWDSDriver(dut)
        self.cs_driver = CS_Driver(dut)

        # Start the clock
        cocotb.start_soon(Clock(self.clk, self.clk_period, units='ns').start())

        # Reset the interface
        cocotb.start_soon(self.reset())

    async def reset(self):
        self.rst.value = 1
        await Timer(10, 'ns')
        
        self.rst.value = 0
        await Timer(10, 'ns')
        
        self.rst.value = 1
        await Timer(10, 'ns')

    async def read(self, address):
        # Simulate a read operation with initial latency
        await Timer(self.initial_latency * self.clk_period, 'ns')  # Initial latency in clock cycles
        data = self.target.read(address, self.data_width // 8)
        return data

    async def write(self, address, data):
        # Simulate a write operation with initial latency
        await Timer(self.initial_latency * self.clk_period, 'ns')  # Initial latency in clock cycles
        self.target.write(address, data, self.data_width // 8)

    async def handle_transactions(self):
        transaction_counter = 0
        ca = [0] * 6  # CA bytes
        while True:
            await RisingEdge(self.clk)
            if self.dut.CS_.value == 0:  # Transaction active
                if transaction_counter == 0:
                    # Drive RWDS during CA phase
                    await self.rwds_driver.drive(0)
                    self.log("Starting new transaction, driving RWDS low")

                if transaction_counter < 6:  # CA phase
                    ca[transaction_counter] = int(self.dut.DQ.value)
                    self.log(f"Received CA byte {transaction_counter}: {ca[transaction_counter]:#04x}")

                if transaction_counter == 5:  # End of CA phase
                    self.log("End of CA phase, starting data phase")
                    # Decode CA
                    command_type = (ca[0] >> 7) & 1
                    address_space = (ca[0] >> 6) & 1
                    burst_type = (ca[0] >> 5) & 1
                    address = self.decode_address(ca)
                    self.log(f"Command Type: {'Read' if command_type else 'Write'}, Address Space: {'Memory' if address_space else 'Register'}, Burst Type: {'Wrapped' if burst_type else 'Linear'}, Address: {address:#04x}")

                if transaction_counter >= 6:  # Data phase
                    if self.dut.RWDS.value == 0:  # Write transaction
                        data = int(self.dut.DQ.value)
                        self.log(f"Write data: {data:#04x}")
                        await self.write(address, data)
                    else:  # Read transaction
                        data = await self.read(address)
                        self.log(f"Read data: {data:#04x}")
                        await self.dq_driver.drive(data)  # Drive data back to the bus

                transaction_counter += 1
                if transaction_counter >= self.burst_length + 6:  # End of transaction
                    transaction_counter = 0
                    await self.rwds_driver.drive_high_impedance()  # End of transaction
                    self.log("Transaction completed, driving RWDS high impedance")

    def decode_address(self, ca):
        # Combine CA bytes to form the address
        address = 0
        for i, byte in enumerate(ca):
            address |= byte << (8 * i)
        # Extract the address part (CA[44:16])
        address = (address >> 16) & ((1 << 29) - 1)
        return address

    def log(self, msg):
        print(f'[{get_sim_time("ns")}]  {msg}')

import cocotb
from cocotb.triggers import Timer, RisingEdge, FallingEdge
from cocotb.clock import Clock

# Import the HyperBusMemory class from hyperbus_memory.py
from hyperbus_memory import HyperBusMemory

@cocotb.test()
async def hyperbus_test(dut):
    # Start the clock
    cocotb.start_soon(Clock(dut.i_clk, 10, units='ns').start())

    # Reset the DUT
    dut.i_rstn.value = 0
    await Timer(100, 'ns')
    dut.i_rstn.value = 1
    await Timer(100, 'ns')
    dut.i_rstn.value = 0

    # Initialize signals
    dut.i_cfg_access.value = 0
    dut.i_mem_valid.value = 0
    dut.i_mem_wstrb.value = 0
    dut.i_mem_addr.value = 0
    dut.i_mem_wdata.value = 0
    dut.i_dq.value = 0
    dut.i_rwds.value = 0

    # Instantiate the HyperBusMemory
    memory = HyperBusMemory(dut, dut.i_clk, dut.i_rstn)

    # Wait for reset to complete
    await Timer(200, 'ns')

    # Perform write transaction
    dut.o_csn0.value = 0  # Start transaction by pulling CS# low
    await Timer(10, 'ns')
    dut.i_mem_valid.value = 1
    dut.i_mem_wstrb.value = 0xF  # Write all bytes
    dut.i_mem_addr.value = 0x1000  # Address 0x1000
    dut.i_mem_wdata.value = 0xDEADBEEF  # Data to write
    await Timer(20, 'ns')
    dut.i_mem_valid.value = 0
    dut.o_csn0.value = 1  # End transaction by pulling CS# high
    await Timer(10, 'ns')

    # Wait for transaction to complete
    await Timer(100, 'ns')

    # Perform read transaction
    dut.o_csn0.value = 0  # Start transaction by pulling CS# low
    await Timer(10, 'ns')
    dut.i_mem_valid.value = 1
    dut.i_mem_wstrb.value = 0  # Read operation
    dut.i_mem_addr.value = 0x1000  # Address 0x1000
    await Timer(20, 'ns')
    dut.i_mem_valid.value = 0
    dut.o_csn0.value = 1  # End transaction by pulling CS# high
    await Timer(10, 'ns')

    # Wait for transaction to complete
    await Timer(100, 'ns')

    # Wait and finish simulation
    await Timer(1000, 'ns')

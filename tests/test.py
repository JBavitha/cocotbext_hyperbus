
# tests/test.py
import cocotb
from cocotb.triggers import Timer
from cocotb.clock import Clock
from cocotbext_hyperbus.HyperBus_Controller import HyperBusController

from cocotbext_hyperbus.hyperbus_memory import DQDriver, RWDSDriver, CS_Driver

@cocotb.test()
async def test_hyperbus(dut):

    clk = dut.i_clk  # Use the correct signal name
    rst = dut.i_rstn  # Use the correct signal name


    # Initialize the clock and reset
    cocotb.start_soon(Clock(clk, 10, units='ns').start())
    await Timer(100, 'ns')
    rst.value = 0
    await Timer(100, 'ns')
    rst.value = 1
    
    # Initialize the drivers
    dq_driver = DQDriver(dut)
    rwds_driver = RWDSDriver(dut)
    cs_driver = CS_Driver(dut)
    
    # Initialize the HyperBusController
    hbc = HyperBusController(dut, dq_driver, rwds_driver, cs_driver)
    await hbc.Reset(dut)
    print("Reset complete")

    # Read from a register
    data = await hbc.ReadReg(0x1000)  
    print(f"Read data from register 0x1000: {data}")

    # Write to memory
    await hbc.WriteMem(0x2000, [0x12345678, 0x87654321])

    # Read from memory
    data = await hbc.ReadMem(0x2000, 2)
    print(f"Read data from memory 0x2000: {[hex(d) for d in data]}")

    # Write random data into memory
    data_count = 16
    w_data = hbc.generate_random_data(data_count)
    w_addr = 0x4000
    await hbc.WriteMem(w_addr, w_data)
    print(f"Random data write operation initiated")
    
    # Read from the memory
    r_addr = w_addr
    r_data = await hbc.ReadMem(r_addr, data_count)

    # Assert the data read matches the data written
    assert w_data == r_data, f"Read-write test failed: expected {w_data}, got {r_data}"

    # End of test
    print("Test completed")

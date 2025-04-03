# defaults
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# Include the wrapper module located in the current directory
VERILOG_SOURCES += wrapper_hbc.v

# Include the hbc module located in the cocotbext_hyperbus directory
VERILOG_SOURCES += ../cocotbext_hyperbus/hbc.v

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL = hbc_wrapper

# MODULE is the filename of the Python test file without the .py extension
MODULE = test_hyperbus_memory

PYTHONPATH := /home/bavitha/Desktop/dyumnin/cocotbext_hyperbus/cocotbext_hyperbus:$(PYTHONPATH)

# Include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim


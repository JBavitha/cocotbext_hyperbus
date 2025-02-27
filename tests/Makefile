# tests/Makefile

# defaults
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# Verilog sources
VERILOG_SOURCES += ../cocotbext_hyperbus/hbc.v

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL = hbc

# MODULE is the filename of the Python test file without the .py extension
MODULE = test

# Include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

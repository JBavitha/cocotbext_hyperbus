# hyperbus_monitor.py
from cocotb.triggers import RisingEdge, Timer
from cocotb.utils import get_sim_time

class HyperBusMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.transactions = []  # List to store captured transactions
        self.ca_phase = []  # List to store CA phase data
        self.data_phase = []  # List to store data phase data

    async def monitor_transactions(self):
        """
        Monitor the HyperBus transactions.
        """
        while True:
            await RisingEdge(self.dut.clk)
            if self.dut.CS_.value == 0:  # Transaction active
                self.ca_phase = []
                self.data_phase = []
                await self.capture_ca_phase()
                await self.capture_data_phase()
                transaction = {
                    'time': get_sim_time('ns'),
                    'ca_phase': self.ca_phase,
                    'data_phase': self.data_phase
                }
                self.log_transaction(transaction)
                self.transactions.append(transaction)

    async def capture_ca_phase(self):
        """
        Capture the CA phase of the transaction.
        """
        for _ in range(6):  # Assuming CA is 6 bytes
            await RisingEdge(self.dut.clk)
            self.ca_phase.append(int(self.dut.DQ.value))

    async def capture_data_phase(self):
        """
        Capture the data phase of the transaction.
        """
        while self.dut.CS_.value == 0:
            await RisingEdge(self.dut.clk)
            self.data_phase.append(int(self.dut.DQ.value))

    def log_transaction(self, transaction):
        """
        Log the captured transaction.
        """
        print(f"[{transaction['time']} ns] CA Phase: {transaction['ca_phase']}, Data Phase: {transaction['data_phase']}")

    def get_transactions(self):
        """
        Return the list of captured transactions.
        """
        return self.transactions

import logging

import numpy as np
from matplotlib import pyplot as plt
from termcolor import colored


class Plotter:
    _packed_data: dict[str, dict[str, int]]

    def __init__(self, packed_data: dict[str, dict[str, int]]) -> None:
        self._packed_data = packed_data

    def _get_descriptors(self) -> list[str]:
        """
        This function returns a list of used descriptors
        :return: A list used descriptors' name
        """
        return list(self._packed_data[list(self._packed_data.keys())[0]].keys())

    def _extract_stats(self) -> dict[str, list[int]]:
        """
        This function returns a dictionary for each descriptor containing # passed tests
        :return: A dictionary passed tests per descriptor
        """
        stats: dict[str, list[int]] = {}
        for descriptor in self._get_descriptors():
            grouping: list[int] = []
            for smart_contract in self._packed_data.keys():
                grouping.append(self._packed_data[smart_contract][descriptor])
            stats[descriptor] = grouping
        return stats

    def plot_results(self) -> None:
        """
        This function plots the computation's results
        """
        smart_contracts: list[str] = list(self._packed_data.keys())
        stats_per_descriptor: dict[str, list[int]] = self._extract_stats()
        num_descriptors: int = len(stats_per_descriptor.keys())
        x = np.arange(len(smart_contracts))
        width: float = 0.90 / num_descriptors
        plt.figure(figsize=(12, 6))
        counter: int = -int(num_descriptors / 2)
        for name, values in stats_per_descriptor.items():
            plt.bar(x + (width * counter), values, width=width, edgecolor="black", label=name)
            counter += 1
        plt.xticks(x, smart_contracts)
        plt.ylabel('Passed Tests')
        plt.xlabel('Smart-Contracts')
        plt.title("Analyzer Results")
        plt.legend(stats_per_descriptor.keys())
        try:
            logging.info(colored("Displaying barplot...", "green"))
            plt.show()
        except KeyboardInterrupt:
            print("\n")  # Fixes no new line after input's prompts
            logging.info(colored("KeyboardInterrupt intercepted, aborting...", "yellow"))

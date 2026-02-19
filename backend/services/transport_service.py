from adapters.transport_adapters import NPTGAdapter, NaPTANAdapter, BusAdapter, RailAdapter

class TransportService:
    def __init__(self):
        self.nptg = NPTGAdapter()
        self.naptan = NaPTANAdapter()
        self.bus = BusAdapter()
        self.rail = RailAdapter()

    def get_gazetteer(self):
        xml_data = self.nptg.fetch_nptg()
        return self.nptg.parse_nptg(xml_data)

    def get_naptan(self, full=False):
        xml_data = self.naptan.fetch_naptan(full=full)
        return self.naptan.parse_naptan(xml_data)

    def get_bus_timetable(self, bus_code):
        return self.bus.fetch_bus_timetable(bus_code)

    def get_bus_live(self, bus_code):
        return self.bus.fetch_bus_live(bus_code)

    def get_rail_corpus(self):
        return self.rail.fetch_corpus()

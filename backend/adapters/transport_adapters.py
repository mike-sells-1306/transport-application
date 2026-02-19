import requests
import xml.etree.ElementTree as ET

BASE_URL = "http://transport.scc.lancs.ac.uk"

class NPTGAdapter:
    def fetch_nptg(self):
        url = f"{BASE_URL}/nptg/nptg.xml"
        response = requests.get(url)
        response.raise_for_status()
        return response.content

    def parse_nptg(self, xml_data):
        root = ET.fromstring(xml_data)
        gazetteer = []
        for entry in root.findall("./GazetteerEntry"):
            code = entry.findtext("NptgLocalityCode")
            name = entry.findtext("LocalityName")
            lat = entry.findtext("Latitude")
            lon = entry.findtext("Longitude")
            gazetteer.append({
                "NptgLocalityCode": code,
                "LocalityName": name,
                "Latitude": lat,
                "Longitude": lon
            })
        return gazetteer

class NaPTANAdapter:
    def fetch_naptan(self, full=False):
        endpoint = "/nptg/naptan-full.xml" if full else "/nptg/naptan.xml"
        url = f"{BASE_URL}{endpoint}"
        response = requests.get(url)
        response.raise_for_status()
        return response.content

    def parse_naptan(self, xml_data):
        root = ET.fromstring(xml_data)
        stops = []
        for stop in root.findall("./StopPoint"):
            atco_code = stop.findtext("AtcoCode")
            naptan_code = stop.findtext("NaptanCode")
            name = stop.findtext("CommonName")
            lat = stop.findtext("Latitude")
            lon = stop.findtext("Longitude")
            stops.append({
                "AtcoCode": atco_code,
                "NaptanCode": naptan_code,
                "Name": name,
                "Latitude": lat,
                "Longitude": lon
            })
        return stops

class BusAdapter:
    def fetch_bus_timetable(self, bus_code):
        url = f"{BASE_URL}/bus/times/{bus_code}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def fetch_bus_live(self, bus_code):
        url = f"{BASE_URL}/bus/live/{bus_code}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

class RailAdapter:
    def fetch_corpus(self):
        url = f"{BASE_URL}/rail/corpus"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

# For live feeds (STOMP/AMQP), placeholder for future implementation
class LiveFeedAdapter:
    def subscribe_train_mvt(self):
        # Placeholder: Would use STOMP/AMQP client to subscribe to /topic/TRAIN_MVT_ALL_TOC
        pass

    def subscribe_td(self):
        # Placeholder: Would use STOMP/AMQP client to subscribe to /topic/TD_ALL_SIG_AREA
        pass

    def subscribe_vstp(self):
        # Placeholder: Would use STOMP/AMQP client to subscribe to /topic/VSTP_ALL
        pass

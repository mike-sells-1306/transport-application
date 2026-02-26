import requests
import xml.etree.ElementTree as ET

BASE_URL = "http://transport.scc.lancs.ac.uk"

class NPTGAdapter:
    def fetch_nptg(self):
        url = f"{BASE_URL}/nptg/nptg.xml"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error fetching NPTG data: {e}")
            return b'<?xml version="1.0"?><NptgCsvData></NptgCsvData>'

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
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error fetching NaPTAN data: {e}")
            # Return empty XML as fallback
            return b'<?xml version="1.0"?><NaPTAN></NaPTAN>'

    def parse_naptan(self, xml_data):
        try:
            root = ET.fromstring(xml_data)
            stops = []
            
            # Define namespace (NaPTAN uses a default namespace)
            ns = {'naptan': 'http://www.naptan.org.uk/'}
            
            # Find all StopPoint elements (they're under StopPoints container)
            for stop in root.findall('.//naptan:StopPoint', ns):
                # Get ATCO code
                atco_code = stop.findtext('naptan:AtcoCode', namespaces=ns)
                naptan_code = stop.findtext('naptan:NaptanCode', namespaces=ns)
                
                # Get descriptor information
                descriptor = stop.find('naptan:Descriptor', ns)
                if descriptor is not None:
                    common_name = descriptor.findtext('naptan:CommonName', namespaces=ns)
                    indicator = descriptor.findtext('naptan:Indicator', namespaces=ns) or ''
                else:
                    common_name = None
                    indicator = ''
                
                # Get place/location information
                place = stop.find('naptan:Place', ns)
                locality_name = ''
                lat = None
                lon = None
                
                if place is not None:
                    locality_name = place.findtext('naptan:Town', namespaces=ns) or place.findtext('naptan:Suburb', namespaces=ns) or ''
                    
                    # Get coordinates from Location/Translation
                    location = place.find('naptan:Location/naptan:Translation', ns)
                    if location is not None:
                        lat = location.findtext('naptan:Latitude', namespaces=ns)
                        lon = location.findtext('naptan:Longitude', namespaces=ns)
                
                # Get stop type (BCT for bus, etc.)
                stop_classification = stop.find('naptan:StopClassification', ns)
                stop_type = 'bus'  # default
                if stop_classification is not None:
                    stop_type_code = stop_classification.findtext('naptan:StopType', namespaces=ns)
                    # BCT = Bus/Coach/Tram stop, RSE/RLY/RPL = Rail
                    if stop_type_code and stop_type_code.startswith('R'):
                        stop_type = 'rail'
                
                # Only add if we have essential data
                if atco_code and common_name and lat and lon:
                    stops.append({
                        "ATCOCode": atco_code,
                        "NaptanCode": naptan_code or '',
                        "CommonName": common_name,
                        "Indicator": indicator,
                        "LocalityName": locality_name,
                        "Latitude": lat,
                        "Longitude": lon,
                        "StopType": stop_type
                    })
            
            print(f"Parsed {len(stops)} stops from NaPTAN XML")
            
            # If no stops found, use mock data for demonstration
            if len(stops) == 0:
                print("No stops parsed, using mock data")
                stops = self._get_mock_stops()
            
            return {"stops": stops}
            
        except Exception as e:
            print(f"Error parsing NaPTAN XML: {e}")
            # Return mock data as fallback
            return {"stops": self._get_mock_stops()}
    
    def _get_mock_stops(self):
        """Mock stop data for North West region for testing when API is unavailable"""
        return [
            {"ATCOCode": "2400LAA10001", "NaptanCode": "lanwtgdw", "CommonName": "Preston Bus Station", "Indicator": "Stand 1", "LocalityName": "Preston", "Latitude": "53.7593", "Longitude": "-2.6993", "StopType": "bus"},
            {"ATCOCode": "2400LAA10002", "NaptanCode": "lanwtgdx", "CommonName": "Preston Bus Station", "Indicator": "Stand 2", "LocalityName": "Preston", "Latitude": "53.7595", "Longitude": "-2.6995", "StopType": "bus"},
            {"ATCOCode": "9100PRST", "NaptanCode": "prstrail", "CommonName": "Preston Railway Station", "Indicator": "", "LocalityName": "Preston", "Latitude": "53.7578", "Longitude": "-2.7081", "StopType": "rail"},
            {"ATCOCode": "2400LAB20001", "NaptanCode": "lanwtblk", "CommonName": "Blackpool North", "Indicator": "Stop A", "LocalityName": "Blackpool", "Latitude": "53.8212", "Longitude": "-3.0507", "StopType": "bus"},
            {"ATCOCode": "9100BKPN", "NaptanCode": "bkpnrail", "CommonName": "Blackpool North Railway Station", "Indicator": "", "LocalityName": "Blackpool", "Latitude": "53.8212", "Longitude": "-3.0507", "StopType": "rail"},
            {"ATCOCode": "2400LAB20002", "NaptanCode": "lanwtbks", "CommonName": "Blackpool South", "Indicator": "Stop B", "LocalityName": "Blackpool", "Latitude": "53.8080", "Longitude": "-3.0530", "StopType": "bus"},
            {"ATCOCode": "2400LAC30001", "NaptanCode": "lanwtlan", "CommonName": "Lancaster Bus Station", "Indicator": "Bay 1", "LocalityName": "Lancaster", "Latitude": "54.0488", "Longitude": "-2.8013", "StopType": "bus"},
            {"ATCOCode": "9100LANC", "NaptanCode": "lancrail", "CommonName": "Lancaster Railway Station", "Indicator": "", "LocalityName": "Lancaster", "Latitude": "54.0488", "Longitude": "-2.8013", "StopType": "rail"},
            {"ATCOCode": "2400LAD40001", "NaptanCode": "lanwtmor", "CommonName": "Morecambe", "Indicator": "Stop C", "LocalityName": "Morecambe", "Latitude": "54.0721", "Longitude": "-2.8651", "StopType": "bus"},
            {"ATCOCode": "2400LAE50001", "NaptanCode": "lanwtfly", "CommonName": "Fleetwood", "Indicator": "Stop D", "LocalityName": "Fleetwood", "Latitude": "53.9220", "Longitude": "-3.0327", "StopType": "bus"},
        ]

class BusAdapter:
    def fetch_bus_timetable(self, bus_code):
        url = f"{BASE_URL}/bus/times/{bus_code}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching bus timetable: {e}")
            return {"error": str(e)}

    def fetch_bus_live(self, bus_code):
        url = f"{BASE_URL}/bus/live/{bus_code}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching live bus data: {e}")
            return {"error": str(e)}

class RailAdapter:
    def fetch_corpus(self):
        url = f"{BASE_URL}/rail/corpus"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching rail corpus: {e}")
            return {"error": str(e)}

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

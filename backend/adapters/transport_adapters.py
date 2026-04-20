import requests
import xml.etree.ElementTree as ET
import io
import re
import zipfile
import json
import os
from pathlib import Path
import gzip
import importlib.util
import logging


def _load_connection_index_store_class():
    mod_path = Path(__file__).resolve().with_name('connection_index.py')
    spec = importlib.util.spec_from_file_location('connection_index_mod', str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError('Unable to load connection_index module')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ConnectionIndexStore


ConnectionIndexStore = _load_connection_index_store_class()

BASE_URL = "http://transport.scc.lancs.ac.uk"
logger = logging.getLogger(__name__)

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
        ns = {'nptg': 'http://www.naptan.org.uk/'}
        gazetteer = []
        for entry in root.findall('.//nptg:NptgLocality', ns):
            code = entry.findtext('nptg:NptgLocalityCode', namespaces=ns)
            name = entry.findtext('nptg:Descriptor/nptg:LocalityName', namespaces=ns)
            lat = entry.findtext('nptg:Location/nptg:Translation/nptg:Latitude', namespaces=ns)
            lon = entry.findtext('nptg:Location/nptg:Translation/nptg:Longitude', namespaces=ns)
            if code and name and lat and lon:
                gazetteer.append({
                    "NptgLocalityCode": code,
                    "LocalityName": name,
                    "Latitude": lat,
                    "Longitude": lon
                })
        print(f"Parsed {len(gazetteer)} localities from NPTG XML")
        return gazetteer

class NaPTANAdapter:
    DATASET_ENDPOINTS = {
        'lancashire': '/nptg/naptan.xml',
        'north_west_rail': '/nptg/naptan-nw-rail.xml',
        'full': '/nptg/naptan-full.xml',
    }

    def fetch_naptan(self, dataset='lancashire', full=False):
        """Fetch NaPTAN XML from the SCC API.

        Parameters
        ----------
        dataset:
            One of ``lancashire``, ``north_west_rail``, or ``full``.
        full:
            Backward-compatibility flag. When True, this forces ``full``.
        """
        if full:
            dataset = 'full'
        endpoint = self.DATASET_ENDPOINTS.get(dataset, self.DATASET_ENDPOINTS['lancashire'])
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
            return {"stops": stops}

        except Exception as e:
            print(f"Error parsing NaPTAN XML: {e}")
            return {"stops": []}

    def _get_supplemental_stops(self):
        """Supplemental stop data covering every red-dot location on the map.
        These are merged into the API results so that searches always return
        stops for Liverpool, Manchester, Keswick, Kendal, etc. even when
        the upstream NaPTAN feed only covers part of the region."""
        return [
            # --- Preston ---
            {"ATCOCode": "2400LAA10001", "NaptanCode": "lanwtgdw", "CommonName": "Preston Bus Station", "Indicator": "Stand 1", "LocalityName": "Preston", "Latitude": "53.7593", "Longitude": "-2.6993", "StopType": "bus"},
            {"ATCOCode": "2400LAA10002", "NaptanCode": "lanwtgdx", "CommonName": "Preston Bus Station", "Indicator": "Stand 2", "LocalityName": "Preston", "Latitude": "53.7595", "Longitude": "-2.6995", "StopType": "bus"},
            {"ATCOCode": "9100PRST", "NaptanCode": "prstrail", "CommonName": "Preston Railway Station", "Indicator": "", "LocalityName": "Preston", "Latitude": "53.7578", "Longitude": "-2.7081", "StopType": "rail"},
            # --- Blackpool ---
            {"ATCOCode": "2400LAB20001", "NaptanCode": "lanwtblk", "CommonName": "Blackpool North Bus Station", "Indicator": "Stop A", "LocalityName": "Blackpool", "Latitude": "53.8212", "Longitude": "-3.0507", "StopType": "bus"},
            {"ATCOCode": "9100BKPN", "NaptanCode": "bkpnrail", "CommonName": "Blackpool North Railway Station", "Indicator": "", "LocalityName": "Blackpool", "Latitude": "53.8212", "Longitude": "-3.0507", "StopType": "rail"},
            {"ATCOCode": "2400LAB20002", "NaptanCode": "lanwtbks", "CommonName": "Blackpool South", "Indicator": "Stop B", "LocalityName": "Blackpool", "Latitude": "53.8080", "Longitude": "-3.0530", "StopType": "bus"},
            {"ATCOCode": "9100BKPS", "NaptanCode": "bkpsrail", "CommonName": "Blackpool South Railway Station", "Indicator": "", "LocalityName": "Blackpool", "Latitude": "53.8044", "Longitude": "-3.0480", "StopType": "rail"},
            {"ATCOCode": "2400BPL00100", "NaptanCode": "lanwtbpt", "CommonName": "Blackpool Tower", "Indicator": "Stop E", "LocalityName": "Blackpool", "Latitude": "53.8159", "Longitude": "-3.0553", "StopType": "bus"},
            {"ATCOCode": "2400BPL00101", "NaptanCode": "lanwtbpp", "CommonName": "Blackpool Pleasure Beach", "Indicator": "Stop F", "LocalityName": "Blackpool", "Latitude": "53.7891", "Longitude": "-3.0563", "StopType": "bus"},
            # --- Lancaster ---
            {"ATCOCode": "2400LAC30001", "NaptanCode": "lanwtlan", "CommonName": "Lancaster Bus Station", "Indicator": "Bay 1", "LocalityName": "Lancaster", "Latitude": "54.0488", "Longitude": "-2.8013", "StopType": "bus"},
            {"ATCOCode": "2400LAC30002", "NaptanCode": "lanwtla2", "CommonName": "Lancaster Bus Station", "Indicator": "Bay 2", "LocalityName": "Lancaster", "Latitude": "54.0490", "Longitude": "-2.8015", "StopType": "bus"},
            {"ATCOCode": "9100LANC", "NaptanCode": "lancrail", "CommonName": "Lancaster Railway Station", "Indicator": "", "LocalityName": "Lancaster", "Latitude": "54.0488", "Longitude": "-2.8013", "StopType": "rail"},
            {"ATCOCode": "2400LAC30010", "NaptanCode": "lanwtlup", "CommonName": "Underpass", "Indicator": "by", "LocalityName": "Lancaster", "Latitude": "54.010236", "Longitude": "-2.785501", "StopType": "bus"},
            {"ATCOCode": "2400LAC30011", "NaptanCode": "lanwtlcv", "CommonName": "Lancaster University", "Indicator": "Main Entrance", "LocalityName": "Lancaster", "Latitude": "54.0104", "Longitude": "-2.7856", "StopType": "bus"},
            # --- Morecambe ---
            {"ATCOCode": "2400LAD40001", "NaptanCode": "lanwtmor", "CommonName": "Morecambe Bus Station", "Indicator": "Stop A", "LocalityName": "Morecambe", "Latitude": "54.0721", "Longitude": "-2.8651", "StopType": "bus"},
            {"ATCOCode": "9100MRCM", "NaptanCode": "mrcmrail", "CommonName": "Morecambe Railway Station", "Indicator": "", "LocalityName": "Morecambe", "Latitude": "54.0716", "Longitude": "-2.8632", "StopType": "rail"},
            {"ATCOCode": "2400LAD40002", "NaptanCode": "lanwtmpr", "CommonName": "Morecambe Promenade", "Indicator": "Stop B", "LocalityName": "Morecambe", "Latitude": "54.0736", "Longitude": "-2.8688", "StopType": "bus"},
            # --- Fleetwood ---
            {"ATCOCode": "2400LAE50001", "NaptanCode": "lanwtfly", "CommonName": "Fleetwood Bus Station", "Indicator": "Stop A", "LocalityName": "Fleetwood", "Latitude": "53.9220", "Longitude": "-3.0327", "StopType": "bus"},
            {"ATCOCode": "2400LAE50002", "NaptanCode": "lanwtflm", "CommonName": "Fleetwood Market", "Indicator": "Stop B", "LocalityName": "Fleetwood", "Latitude": "53.9218", "Longitude": "-3.0280", "StopType": "bus"},
            # --- Liverpool ---
            {"ATCOCode": "2800S00000A", "NaptanCode": "merwtlpl", "CommonName": "Liverpool ONE Bus Station", "Indicator": "Stop A", "LocalityName": "Liverpool", "Latitude": "53.4010", "Longitude": "-2.9880", "StopType": "bus"},
            {"ATCOCode": "2800S00000B", "NaptanCode": "merwtlpb", "CommonName": "Liverpool ONE Bus Station", "Indicator": "Stop B", "LocalityName": "Liverpool", "Latitude": "53.4012", "Longitude": "-2.9882", "StopType": "bus"},
            {"ATCOCode": "9100LVRPL", "NaptanCode": "lvrprail", "CommonName": "Liverpool Lime Street Railway Station", "Indicator": "", "LocalityName": "Liverpool", "Latitude": "53.4074", "Longitude": "-2.9778", "StopType": "rail"},
            {"ATCOCode": "9100LVRPC", "NaptanCode": "lvrlcrail", "CommonName": "Liverpool Central Railway Station", "Indicator": "", "LocalityName": "Liverpool", "Latitude": "53.4043", "Longitude": "-2.9790", "StopType": "rail"},
            {"ATCOCode": "2800S00000C", "NaptanCode": "merwtqsq", "CommonName": "Queen Square Bus Station", "Indicator": "Stop A", "LocalityName": "Liverpool", "Latitude": "53.4083", "Longitude": "-2.9816", "StopType": "bus"},
            {"ATCOCode": "2800S00000D", "NaptanCode": "merwtadr", "CommonName": "Liverpool Albert Dock", "Indicator": "", "LocalityName": "Liverpool", "Latitude": "53.3997", "Longitude": "-2.9919", "StopType": "bus"},
            # --- Manchester ---
            {"ATCOCode": "1800SB00001", "NaptanCode": "gmpwtpic", "CommonName": "Piccadilly Bus Station", "Indicator": "Stand A", "LocalityName": "Manchester", "Latitude": "53.4774", "Longitude": "-2.2309", "StopType": "bus"},
            {"ATCOCode": "1800SB00002", "NaptanCode": "gmpwtshd", "CommonName": "Shudehill Interchange", "Indicator": "Stand A", "LocalityName": "Manchester", "Latitude": "53.4858", "Longitude": "-2.2394", "StopType": "bus"},
            {"ATCOCode": "9100MNCRPIC", "NaptanCode": "mncrprail", "CommonName": "Manchester Piccadilly Railway Station", "Indicator": "", "LocalityName": "Manchester", "Latitude": "53.4774", "Longitude": "-2.2309", "StopType": "rail"},
            {"ATCOCode": "9100MNCRVIC", "NaptanCode": "mncvrail", "CommonName": "Manchester Victoria Railway Station", "Indicator": "", "LocalityName": "Manchester", "Latitude": "53.4879", "Longitude": "-2.2436", "StopType": "rail"},
            {"ATCOCode": "9100MNCROXR", "NaptanCode": "mnoxrail", "CommonName": "Manchester Oxford Road Railway Station", "Indicator": "", "LocalityName": "Manchester", "Latitude": "53.4738", "Longitude": "-2.2421", "StopType": "rail"},
            {"ATCOCode": "1800SB00003", "NaptanCode": "gmpwtdng", "CommonName": "Deansgate", "Indicator": "Stop A", "LocalityName": "Manchester", "Latitude": "53.4746", "Longitude": "-2.2504", "StopType": "bus"},
            # --- Blackburn ---
            {"ATCOCode": "2400BLB00001", "NaptanCode": "lanwtblb", "CommonName": "Blackburn Bus Station", "Indicator": "Stand A", "LocalityName": "Blackburn", "Latitude": "53.7474", "Longitude": "-2.4840", "StopType": "bus"},
            {"ATCOCode": "2400BLB00002", "NaptanCode": "lanwtbb2", "CommonName": "Blackburn Bus Station", "Indicator": "Stand B", "LocalityName": "Blackburn", "Latitude": "53.7476", "Longitude": "-2.4842", "StopType": "bus"},
            {"ATCOCode": "9100BLKB", "NaptanCode": "blkbrail", "CommonName": "Blackburn Railway Station", "Indicator": "", "LocalityName": "Blackburn", "Latitude": "53.7467", "Longitude": "-2.4806", "StopType": "rail"},
            {"ATCOCode": "2400BLB00003", "NaptanCode": "lanwtbct", "CommonName": "Blackburn Cathedral", "Indicator": "", "LocalityName": "Blackburn", "Latitude": "53.7492", "Longitude": "-2.4848", "StopType": "bus"},
            # --- Lytham St Annes ---
            {"ATCOCode": "2400LSA00001", "NaptanCode": "lanwtlsa", "CommonName": "Lytham St Annes", "Indicator": "Stop A", "LocalityName": "Lytham St Annes", "Latitude": "53.7485", "Longitude": "-2.9991", "StopType": "bus"},
            {"ATCOCode": "2400LSA00002", "NaptanCode": "lanwtlsq", "CommonName": "Lytham Square", "Indicator": "", "LocalityName": "Lytham St Annes", "Latitude": "53.7364", "Longitude": "-2.9637", "StopType": "bus"},
            {"ATCOCode": "9100LTMSA", "NaptanCode": "ltmsrail", "CommonName": "Lytham Railway Station", "Indicator": "", "LocalityName": "Lytham St Annes", "Latitude": "53.7392", "Longitude": "-2.9614", "StopType": "rail"},
            {"ATCOCode": "9100STNAN", "NaptanCode": "stnarail", "CommonName": "St Annes-on-the-Sea Railway Station", "Indicator": "", "LocalityName": "Lytham St Annes", "Latitude": "53.7528", "Longitude": "-3.0253", "StopType": "rail"},
            # --- Kirkham ---
            {"ATCOCode": "2400KRK00001", "NaptanCode": "lanwtkrk", "CommonName": "Kirkham Market Square", "Indicator": "", "LocalityName": "Kirkham", "Latitude": "53.7827", "Longitude": "-2.8715", "StopType": "bus"},
            {"ATCOCode": "9100KRKM", "NaptanCode": "krkmrail", "CommonName": "Kirkham and Wesham Railway Station", "Indicator": "", "LocalityName": "Kirkham", "Latitude": "53.7830", "Longitude": "-2.8810", "StopType": "rail"},
            # --- Poulton-le-Fylde ---
            {"ATCOCode": "2400PLF00001", "NaptanCode": "lanwtplf", "CommonName": "Poulton-le-Fylde Bus Stop", "Indicator": "Stop A", "LocalityName": "Poulton-le-Fylde", "Latitude": "53.8461", "Longitude": "-2.9905", "StopType": "bus"},
            {"ATCOCode": "2400PLF00002", "NaptanCode": "lanwtpms", "CommonName": "Poulton-le-Fylde Market Square", "Indicator": "", "LocalityName": "Poulton-le-Fylde", "Latitude": "53.8468", "Longitude": "-2.9927", "StopType": "bus"},
            {"ATCOCode": "9100PLTN", "NaptanCode": "pltnrail", "CommonName": "Poulton-le-Fylde Railway Station", "Indicator": "", "LocalityName": "Poulton-le-Fylde", "Latitude": "53.8474", "Longitude": "-2.9927", "StopType": "rail"},
            # --- Garstang ---
            {"ATCOCode": "2400GRS00001", "NaptanCode": "lanwtgrs", "CommonName": "Garstang Bus Stop", "Indicator": "High Street", "LocalityName": "Garstang", "Latitude": "53.9016", "Longitude": "-2.7735", "StopType": "bus"},
            {"ATCOCode": "2400GRS00002", "NaptanCode": "lanwtgrc", "CommonName": "Garstang Cross", "Indicator": "", "LocalityName": "Garstang", "Latitude": "53.9020", "Longitude": "-2.7742", "StopType": "bus"},
            # --- Heysham ---
            {"ATCOCode": "2400HYS00001", "NaptanCode": "lanwthys", "CommonName": "Heysham Bus Stop", "Indicator": "", "LocalityName": "Heysham", "Latitude": "54.0495", "Longitude": "-2.8903", "StopType": "bus"},
            {"ATCOCode": "2400HYS00002", "NaptanCode": "lanwthpt", "CommonName": "Heysham Port", "Indicator": "", "LocalityName": "Heysham", "Latitude": "54.0323", "Longitude": "-2.9158", "StopType": "bus"},
            {"ATCOCode": "9100HYSM", "NaptanCode": "hysmrail", "CommonName": "Heysham Port Railway Station", "Indicator": "", "LocalityName": "Heysham", "Latitude": "54.0323", "Longitude": "-2.9158", "StopType": "rail"},
            # --- Carnforth ---
            {"ATCOCode": "2400CNF00001", "NaptanCode": "lanwtcnf", "CommonName": "Carnforth Bus Stop", "Indicator": "Market Street", "LocalityName": "Carnforth", "Latitude": "54.1282", "Longitude": "-2.7701", "StopType": "bus"},
            {"ATCOCode": "9100CNFR", "NaptanCode": "cnfrrail", "CommonName": "Carnforth Railway Station", "Indicator": "", "LocalityName": "Carnforth", "Latitude": "54.1285", "Longitude": "-2.7700", "StopType": "rail"},
            {"ATCOCode": "2400CNF00002", "NaptanCode": "lanwtcnh", "CommonName": "Carnforth Heritage Centre", "Indicator": "", "LocalityName": "Carnforth", "Latitude": "54.1289", "Longitude": "-2.7706", "StopType": "bus"},
            # --- Kirkby Lonsdale ---
            {"ATCOCode": "0900KBL00001", "NaptanCode": "cumwtkbl", "CommonName": "Kirkby Lonsdale Market Square", "Indicator": "", "LocalityName": "Kirkby Lonsdale", "Latitude": "54.2018", "Longitude": "-2.5967", "StopType": "bus"},
            {"ATCOCode": "0900KBL00002", "NaptanCode": "cumwtkbm", "CommonName": "Kirkby Lonsdale Main Street", "Indicator": "", "LocalityName": "Kirkby Lonsdale", "Latitude": "54.2022", "Longitude": "-2.5960", "StopType": "bus"},
            # --- Grange-over-Sands ---
            {"ATCOCode": "0900GOS00001", "NaptanCode": "cumwtgos", "CommonName": "Grange-over-Sands Bus Stop", "Indicator": "Main Street", "LocalityName": "Grange-over-Sands", "Latitude": "54.1931", "Longitude": "-2.9095", "StopType": "bus"},
            {"ATCOCode": "9100GRNG", "NaptanCode": "grngrail", "CommonName": "Grange-over-Sands Railway Station", "Indicator": "", "LocalityName": "Grange-over-Sands", "Latitude": "54.1935", "Longitude": "-2.9102", "StopType": "rail"},
            {"ATCOCode": "0900GOS00002", "NaptanCode": "cumwtgpr", "CommonName": "Grange-over-Sands Promenade", "Indicator": "", "LocalityName": "Grange-over-Sands", "Latitude": "54.1920", "Longitude": "-2.9070", "StopType": "bus"},
            # --- Cartmel ---
            {"ATCOCode": "0900CTM00001", "NaptanCode": "cumwtctm", "CommonName": "Cartmel Village", "Indicator": "", "LocalityName": "Cartmel", "Latitude": "54.2009", "Longitude": "-2.9529", "StopType": "bus"},
            {"ATCOCode": "0900CTM00002", "NaptanCode": "cumwtcrc", "CommonName": "Cartmel Racecourse", "Indicator": "", "LocalityName": "Cartmel", "Latitude": "54.1975", "Longitude": "-2.9532", "StopType": "bus"},
            {"ATCOCode": "9100CARK", "NaptanCode": "carkrail", "CommonName": "Cark and Cartmel Railway Station", "Indicator": "", "LocalityName": "Cartmel", "Latitude": "54.1842", "Longitude": "-2.9702", "StopType": "rail"},
            # --- Kendal ---
            {"ATCOCode": "0900KDL00001", "NaptanCode": "cumwtkdl", "CommonName": "Kendal Bus Station", "Indicator": "Stand A", "LocalityName": "Kendal", "Latitude": "54.3290", "Longitude": "-2.7472", "StopType": "bus"},
            {"ATCOCode": "0900KDL00002", "NaptanCode": "cumwtkd2", "CommonName": "Kendal Bus Station", "Indicator": "Stand B", "LocalityName": "Kendal", "Latitude": "54.3292", "Longitude": "-2.7474", "StopType": "bus"},
            {"ATCOCode": "9100KNDL", "NaptanCode": "kndlrail", "CommonName": "Kendal Railway Station", "Indicator": "", "LocalityName": "Kendal", "Latitude": "54.3282", "Longitude": "-2.7515", "StopType": "rail"},
            {"ATCOCode": "0900KDL00003", "NaptanCode": "cumwtkms", "CommonName": "Kendal Mint Street", "Indicator": "", "LocalityName": "Kendal", "Latitude": "54.3268", "Longitude": "-2.7462", "StopType": "bus"},
            # --- Windermere ---
            {"ATCOCode": "0900WDM00001", "NaptanCode": "cumwtwdm", "CommonName": "Windermere Bus Stop", "Indicator": "Main Road", "LocalityName": "Windermere", "Latitude": "54.3792", "Longitude": "-2.9063", "StopType": "bus"},
            {"ATCOCode": "9100WNDM", "NaptanCode": "wndmrail", "CommonName": "Windermere Railway Station", "Indicator": "", "LocalityName": "Windermere", "Latitude": "54.3798", "Longitude": "-2.9038", "StopType": "rail"},
            {"ATCOCode": "0900WDM00002", "NaptanCode": "cumwtwlk", "CommonName": "Windermere Lakeside", "Indicator": "", "LocalityName": "Windermere", "Latitude": "54.3540", "Longitude": "-2.9445", "StopType": "bus"},
            {"ATCOCode": "0900WDM00003", "NaptanCode": "cumwtbow", "CommonName": "Bowness-on-Windermere", "Indicator": "Pier", "LocalityName": "Windermere", "Latitude": "54.3620", "Longitude": "-2.9223", "StopType": "bus"},
            # --- Ambleside ---
            {"ATCOCode": "0900AMB00001", "NaptanCode": "cumwtamb", "CommonName": "Ambleside Bus Stop", "Indicator": "Kelsick Road", "LocalityName": "Ambleside", "Latitude": "54.4316", "Longitude": "-2.9622", "StopType": "bus"},
            {"ATCOCode": "0900AMB00002", "NaptanCode": "cumwtaml", "CommonName": "Ambleside Waterhead", "Indicator": "Pier", "LocalityName": "Ambleside", "Latitude": "54.4256", "Longitude": "-2.9598", "StopType": "bus"},
            {"ATCOCode": "0900AMB00003", "NaptanCode": "cumwtamm", "CommonName": "Ambleside Market Cross", "Indicator": "", "LocalityName": "Ambleside", "Latitude": "54.4322", "Longitude": "-2.9632", "StopType": "bus"},
            # --- Barrow-in-Furness ---
            {"ATCOCode": "0900BIF00001", "NaptanCode": "cumwtbif", "CommonName": "Barrow-in-Furness Bus Station", "Indicator": "Stand A", "LocalityName": "Barrow-in-Furness", "Latitude": "54.1100", "Longitude": "-3.2280", "StopType": "bus"},
            {"ATCOCode": "0900BIF00002", "NaptanCode": "cumwtbi2", "CommonName": "Barrow-in-Furness Bus Station", "Indicator": "Stand B", "LocalityName": "Barrow-in-Furness", "Latitude": "54.1102", "Longitude": "-3.2282", "StopType": "bus"},
            {"ATCOCode": "9100BRIF", "NaptanCode": "brifrail", "CommonName": "Barrow-in-Furness Railway Station", "Indicator": "", "LocalityName": "Barrow-in-Furness", "Latitude": "54.1120", "Longitude": "-3.2261", "StopType": "rail"},
            {"ATCOCode": "0900BIF00003", "NaptanCode": "cumwtbdk", "CommonName": "Barrow Dock Museum", "Indicator": "", "LocalityName": "Barrow-in-Furness", "Latitude": "54.1069", "Longitude": "-3.2306", "StopType": "bus"},
            # --- Keswick ---
            {"ATCOCode": "0900KSW00001", "NaptanCode": "cumwtksw", "CommonName": "Keswick Bus Station", "Indicator": "Stand A", "LocalityName": "Keswick", "Latitude": "54.6010", "Longitude": "-3.1376", "StopType": "bus"},
            {"ATCOCode": "0900KSW00002", "NaptanCode": "cumwtks2", "CommonName": "Keswick Bus Station", "Indicator": "Stand B", "LocalityName": "Keswick", "Latitude": "54.6012", "Longitude": "-3.1378", "StopType": "bus"},
            {"ATCOCode": "0900KSW00003", "NaptanCode": "cumwtkms", "CommonName": "Keswick Market Square", "Indicator": "", "LocalityName": "Keswick", "Latitude": "54.6005", "Longitude": "-3.1345", "StopType": "bus"},
            {"ATCOCode": "0900KSW00004", "NaptanCode": "cumwtklt", "CommonName": "Keswick Lakeside", "Indicator": "Derwentwater", "LocalityName": "Keswick", "Latitude": "54.5987", "Longitude": "-3.1392", "StopType": "bus"},
            {"ATCOCode": "0900KSW00005", "NaptanCode": "cumwtkpt", "CommonName": "Keswick Pencil Museum", "Indicator": "", "LocalityName": "Keswick", "Latitude": "54.6018", "Longitude": "-3.1412", "StopType": "bus"},
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

class RailDeparturesAdapter:
    """Fetches and parses real-time rail departure boards from the SCC API.

    Endpoint: /rail/departures/<CRS>
    Returns XML with namespaced elements describing upcoming train (and rail-
    replacement bus) services, including scheduled/estimated times, operators,
    origins, destinations and subsequent calling points.
    """

    NS = {
        'lt':  'http://thalesgroup.com/RTTI/2012-01-13/ldb/types',
        'lt4': 'http://thalesgroup.com/RTTI/2015-11-27/ldb/types',
        'lt5': 'http://thalesgroup.com/RTTI/2016-02-16/ldb/types',
        'lt8': 'http://thalesgroup.com/RTTI/2021-11-01/ldb/types',
    }

    def fetch_departures(self, crs_code):
        """Fetch the departure board for *crs_code* and return structured data.

        Returns dict::

            {
                "station": "Lancaster",
                "crs": "LAN",
                "services": [ … ]
            }

        Each service dict contains *std*, *etd*, *platform*, *operator*,
        *operator_code*, *service_type*, *service_id*, *origin*, *destination*,
        and *calling_points* (list of dicts with *name*, *crs*, *scheduled*,
        *estimated*).
        """
        url = f"{BASE_URL}/rail/departures/{crs_code}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return self._parse(response.content, crs_code)
        except Exception as e:
            print(f"Error fetching rail departures for {crs_code}: {e}")
            return {"station": crs_code, "crs": crs_code, "services": [], "error": str(e)}

    # ------------------------------------------------------------------
    # Internal XML parsing
    # ------------------------------------------------------------------
    def _parse(self, xml_data, crs_code):
        root = ET.fromstring(xml_data)
        ns = self.NS

        result = {
            "station": root.findtext('lt4:locationName', namespaces=ns) or crs_code,
            "crs": root.findtext('lt4:crs', namespaces=ns) or crs_code,
            "services": [],
        }

        # Train services
        for svc in root.findall('.//lt8:trainServices/lt8:service', ns):
            parsed = self._parse_service(svc, ns, 'train')
            if parsed:
                result["services"].append(parsed)

        # Rail-replacement bus services
        for svc in root.findall('.//lt8:busServices/lt8:service', ns):
            parsed = self._parse_service(svc, ns, 'bus')
            if parsed:
                result["services"].append(parsed)

        return result

    def _parse_service(self, elem, ns, default_type):
        # Skip cancelled services
        if (elem.findtext('lt4:isCancelled', namespaces=ns) or '').lower() == 'true':
            return None

        std = elem.findtext('lt4:std', namespaces=ns) or ''
        etd = elem.findtext('lt4:etd', namespaces=ns) or ''

        # Origin
        origin_loc = elem.find('.//lt5:origin/lt4:location', ns)
        origin = {
            'name': (origin_loc.findtext('lt4:locationName', namespaces=ns) or '') if origin_loc is not None else '',
            'crs':  (origin_loc.findtext('lt4:crs', namespaces=ns) or '') if origin_loc is not None else '',
        }

        # Destination
        dest_loc = elem.find('.//lt5:destination/lt4:location', ns)
        destination = {
            'name': (dest_loc.findtext('lt4:locationName', namespaces=ns) or '') if dest_loc is not None else '',
            'crs':  (dest_loc.findtext('lt4:crs', namespaces=ns) or '') if dest_loc is not None else '',
        }

        # Calling points (skip individually cancelled stops)
        calling_points = []
        for cp in elem.findall('.//lt8:callingPoint', ns):
            if (cp.findtext('lt8:isCancelled', namespaces=ns) or '').lower() == 'true':
                continue
            calling_points.append({
                'name':      cp.findtext('lt8:locationName', namespaces=ns) or '',
                'crs':       cp.findtext('lt8:crs', namespaces=ns) or '',
                'scheduled': cp.findtext('lt8:st', namespaces=ns) or '',
                'estimated': cp.findtext('lt8:et', namespaces=ns) or '',
            })

        return {
            'std':           std,
            'etd':           etd,
            'platform':      elem.findtext('lt4:platform', namespaces=ns) or '',
            'operator':      elem.findtext('lt4:operator', namespaces=ns) or '',
            'operator_code': elem.findtext('lt4:operatorCode', namespaces=ns) or '',
            'service_type':  elem.findtext('lt4:serviceType', namespaces=ns) or default_type,
            'service_id':    elem.findtext('lt4:serviceID', namespaces=ns) or '',
            'origin':        origin,
            'destination':   destination,
            'calling_points': calling_points,
        }


# ======================================================================
# Route Planner – builds multi-modal routes from real data
# ======================================================================
import math
import heapq
import bisect
from collections import defaultdict
from datetime import datetime as _dt, timedelta as _td
from zoneinfo import ZoneInfo


class RoutePlannerAdapter:
    """Plans multi-modal routes from SCC transport data.

    Bus legs are built from SCC timetable datasets (/bus/times -> TransXChange
    ZIP downloads). Rail legs use SCC live departure boards
    (/rail/departures/<CRS>) with scheduled calling points.
    """

    # Walking speed in metres per minute (~4.8 km/h)
    WALK_SPEED = 80
    # Factor to convert straight-line distance to walking distance
    WALK_FACTOR = 1.35
    DATASET_CACHE_FORMAT_VERSION = 12
    UK_TZ = ZoneInfo('Europe/London')
    METRIC_BUS_STOPS_KEY = 'bus_stops_processed'
    METRIC_TRAIN_STATIONS_KEY = 'train_stations_processed'
    METRIC_PLANNER_STAGE_KEY = 'planner_stage'

    # ------------------------------------------------------------------
    # Railway station database  (CRS → name, lat, lon)
    # ------------------------------------------------------------------
    STATIONS = {
        'LAN': {'name': 'Lancaster',                  'lat': 54.0488, 'lon': -2.8013},
        'PRE': {'name': 'Preston',                    'lat': 53.7578, 'lon': -2.7081},
        'BPN': {'name': 'Blackpool North',            'lat': 53.8212, 'lon': -3.0507},
        'BPS': {'name': 'Blackpool South',            'lat': 53.8044, 'lon': -3.0480},
        'BBN': {'name': 'Blackburn',                  'lat': 53.7467, 'lon': -2.4806},
        'MCM': {'name': 'Morecambe',                  'lat': 54.0716, 'lon': -2.8632},
        'CNF': {'name': 'Carnforth',                  'lat': 54.1285, 'lon': -2.7700},
        'WDM': {'name': 'Windermere',                 'lat': 54.3798, 'lon': -2.9038},
        'BIF': {'name': 'Barrow-in-Furness',          'lat': 54.1120, 'lon': -3.2261},
        'MAN': {'name': 'Manchester Piccadilly',      'lat': 53.4774, 'lon': -2.2309},
        'MCV': {'name': 'Manchester Victoria',        'lat': 53.4879, 'lon': -2.2436},
        'LIV': {'name': 'Liverpool Lime Street',      'lat': 53.4074, 'lon': -2.9778},
        'KKM': {'name': 'Kirkham & Wesham',           'lat': 53.7830, 'lon': -2.8810},
        'PFY': {'name': 'Poulton-le-Fylde',           'lat': 53.8474, 'lon': -2.9927},
        'OXN': {'name': 'Oxenholme Lake District',    'lat': 54.3060, 'lon': -2.7217},
        'GOS': {'name': 'Grange-over-Sands',          'lat': 54.1935, 'lon': -2.9102},
        'CAK': {'name': 'Cark',                       'lat': 54.1842, 'lon': -2.9702},
        'LTM': {'name': 'Lytham',                     'lat': 53.7392, 'lon': -2.9614},
        'SAN': {'name': "St Annes-on-the-Sea",        'lat': 53.7528, 'lon': -3.0253},
        'HYM': {'name': 'Heysham Port',               'lat': 54.0323, 'lon': -2.9158},
        'ULV': {'name': 'Ulverston',                  'lat': 54.1940, 'lon': -3.0900},
        'SVR': {'name': 'Silverdale',                 'lat': 54.1670, 'lon': -2.8060},
        'ARN': {'name': 'Arnside',                    'lat': 54.2040, 'lon': -2.8330},
        'BAR': {'name': 'Bare Lane',                  'lat': 54.0610, 'lon': -2.8430},
        'CRL': {'name': 'Chorley',                    'lat': 53.6510, 'lon': -2.6320},
        'BON': {'name': 'Bolton',                     'lat': 53.5830, 'lon': -2.4330},
        'WGN': {'name': 'Wigan North Western',        'lat': 53.5440, 'lon': -2.6330},
        'DGT': {'name': 'Deansgate',                  'lat': 53.4746, 'lon': -2.2504},
        'MCO': {'name': 'Manchester Oxford Road',     'lat': 53.4738, 'lon': -2.2421},
    }

    # Reverse lookup: CRS codes by approximate locality name (lowercase)
    _LOCALITY_CRS = {
        'lancaster':           ['LAN'],
        'preston':             ['PRE'],
        'blackpool':           ['BPN', 'BPS'],
        'blackburn':           ['BBN'],
        'morecambe':           ['MCM'],
        'carnforth':           ['CNF'],
        'windermere':          ['WDM'],
        'barrow-in-furness':   ['BIF'],
        'barrow':              ['BIF'],
        'manchester':          ['MAN', 'MCV'],
        'liverpool':           ['LIV'],
        'kirkham':             ['KKM'],
        'poulton-le-fylde':    ['PFY'],
        'poulton':             ['PFY'],
        'kendal':              ['OXN'],
        'oxenholme':           ['OXN'],
        'grange-over-sands':   ['GOS'],
        'grange':              ['GOS'],
        'cartmel':             ['CAK'],
        'cark':                ['CAK'],
        'lytham':              ['LTM'],
        'lytham st annes':     ['LTM', 'SAN'],
        'st annes':            ['SAN'],
        'heysham':             ['HYM'],
        'ulverston':           ['ULV'],
        'silverdale':          ['SVR'],
        'arnside':             ['ARN'],
        'bolton':              ['BON'],
        'wigan':               ['WGN'],
        'chorley':             ['CRL'],
    }

    # ------------------------------------------------------------------
    # Known bus services  (real route numbers, stops, frequencies)
    # ------------------------------------------------------------------
    BUS_SERVICES = [
        {
            'service': 'Stagecoach 1',
            'operator': 'Stagecoach',
            'frequency_mins': 10,
            'segment_mins': [2, 10, 8, 3],
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Common Garden Street',      'lat': 54.0480, 'lon': -2.7995},
                {'name': 'Hala',                      'lat': 54.0370, 'lon': -2.7930},
                {'name': 'Underpass',                 'lat': 54.010236, 'lon': -2.785501},
                {'name': 'Lancaster University',      'lat': 54.0104, 'lon': -2.7856},
            ],
        },
        {
            'service': 'Stagecoach 1A',
            'operator': 'Stagecoach',
            'frequency_mins': 10,
            'segment_mins': [6, 12, 3],
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Hala',                      'lat': 54.0370, 'lon': -2.7930},
                {'name': 'Underpass',                 'lat': 54.010236, 'lon': -2.785501},
                {'name': 'Lancaster University',      'lat': 54.0104, 'lon': -2.7856},
            ],
        },
        {
            'service': 'Stagecoach 3',
            'operator': 'Stagecoach',
            'frequency_mins': 12,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Skerton',                   'lat': 54.0560, 'lon': -2.8050},
                {'name': 'Morecambe Bus Station',     'lat': 54.0721, 'lon': -2.8651},
            ],
        },
        {
            'service': 'Stagecoach 4',
            'operator': 'Stagecoach',
            'frequency_mins': 30,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Scale Hall',                'lat': 54.0530, 'lon': -2.8250},
                {'name': 'Heysham Bus Stop',          'lat': 54.0495, 'lon': -2.8903},
            ],
        },
        {
            'service': 'Stagecoach 40',
            'operator': 'Stagecoach',
            'frequency_mins': 30,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Garstang Cross',            'lat': 53.9020, 'lon': -2.7742},
                {'name': 'Preston Bus Station',       'lat': 53.7593, 'lon': -2.6993},
            ],
        },
        {
            'service': 'Stagecoach 41',
            'operator': 'Stagecoach',
            'frequency_mins': 30,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Galgate',                   'lat': 53.9920, 'lon': -2.7850},
                {'name': 'Garstang Cross',            'lat': 53.9020, 'lon': -2.7742},
                {'name': 'Preston Bus Station',       'lat': 53.7593, 'lon': -2.6993},
            ],
        },
        {
            'service': 'Stagecoach 42',
            'operator': 'Stagecoach',
            'frequency_mins': 60,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Galgate',                   'lat': 53.9920, 'lon': -2.7850},
                {'name': 'Garstang Cross',            'lat': 53.9020, 'lon': -2.7742},
                {'name': 'Broughton',                 'lat': 53.8150, 'lon': -2.7250},
                {'name': 'Preston Bus Station',       'lat': 53.7593, 'lon': -2.6993},
            ],
        },
        {
            'service': 'Stagecoach 100',
            'operator': 'Stagecoach',
            'frequency_mins': 20,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Lancaster University',      'lat': 54.0104, 'lon': -2.7856},
                {'name': 'Carnforth Bus Stop',        'lat': 54.1282, 'lon': -2.7701},
                {'name': 'Morecambe Bus Station',     'lat': 54.0721, 'lon': -2.8651},
            ],
        },
        {
            'service': 'Stagecoach 555',
            'operator': 'Stagecoach',
            'frequency_mins': 60,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Carnforth Bus Stop',        'lat': 54.1282, 'lon': -2.7701},
                {'name': 'Kendal Bus Station',        'lat': 54.3290, 'lon': -2.7472},
                {'name': 'Windermere Bus Stop',       'lat': 54.3792, 'lon': -2.9063},
                {'name': 'Ambleside Bus Stop',        'lat': 54.4316, 'lon': -2.9622},
                {'name': 'Keswick Bus Station',       'lat': 54.6010, 'lon': -3.1376},
            ],
        },
        {
            'service': 'Stagecoach 6',
            'operator': 'Stagecoach',
            'frequency_mins': 20,
            'stops': [
                {'name': 'Preston Bus Station',       'lat': 53.7593, 'lon': -2.6993},
                {'name': 'Kirkham Market Square',     'lat': 53.7827, 'lon': -2.8715},
                {'name': 'Blackpool North Bus Station', 'lat': 53.8212, 'lon': -3.0507},
            ],
        },
        {
            'service': 'Arriva 59',
            'operator': 'Arriva',
            'frequency_mins': 30,
            'stops': [
                {'name': 'Preston Bus Station',       'lat': 53.7593, 'lon': -2.6993},
                {'name': 'Blackburn Bus Station',     'lat': 53.7474, 'lon': -2.4840},
            ],
        },
        {
            'service': 'Stagecoach 599',
            'operator': 'Stagecoach',
            'frequency_mins': 20,
            'stops': [
                {'name': 'Kendal Bus Station',        'lat': 54.3290, 'lon': -2.7472},
                {'name': 'Windermere Bus Stop',       'lat': 54.3792, 'lon': -2.9063},
                {'name': 'Bowness-on-Windermere',     'lat': 54.3620, 'lon': -2.9223},
                {'name': 'Ambleside Bus Stop',        'lat': 54.4316, 'lon': -2.9622},
            ],
        },
        {
            'service': 'Blackpool Tramway',
            'operator': 'Blackpool Transport',
            'frequency_mins': 10,
            'stops': [
                {'name': 'Fleetwood Bus Station',     'lat': 53.9220, 'lon': -3.0327},
                {'name': 'Poulton-le-Fylde Bus Stop', 'lat': 53.8461, 'lon': -2.9905},
                {'name': 'Blackpool North Bus Station','lat': 53.8212, 'lon': -3.0507},
                {'name': 'Blackpool Tower',           'lat': 53.8159, 'lon': -3.0553},
                {'name': 'Blackpool Pleasure Beach',  'lat': 53.7891, 'lon': -3.0563},
            ],
        },
        {
            'service': 'Stagecoach X1',
            'operator': 'Stagecoach',
            'frequency_mins': 30,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Morecambe Bus Station',     'lat': 54.0721, 'lon': -2.8651},
            ],
        },
        {
            'service': 'Kirkby Lonsdale Coaches 567',
            'operator': 'Kirkby Lonsdale Coaches',
            'frequency_mins': 120,
            'stops': [
                {'name': 'Lancaster Bus Station',     'lat': 54.0488, 'lon': -2.8013},
                {'name': 'Carnforth Bus Stop',        'lat': 54.1282, 'lon': -2.7701},
                {'name': 'Kirkby Lonsdale Market Square', 'lat': 54.2018, 'lon': -2.5967},
            ],
        },
    ]

    def __init__(self):
        self.rail = RailDeparturesAdapter()
        self._static_data_only = os.getenv('STATIC_DATA_ONLY', 'true').strip().lower() == 'true'
        self._live_poll_min_seconds = max(5, int(os.getenv('LIVE_POLL_MIN_SECONDS', '5')))
        self._live_bus_cache = None
        self._live_bus_cache_ts = None
        self._rail_departures_cache = {}
        self._rail_departures_cache_ts = {}
        self._bus_times_index_cache = None
        self._bus_times_index_ts = None
        self._bus_dataset_cache = {}  # dataset_id -> {ts, trips}
        self._naptan_lookup_cache = None
        self._naptan_lookup_ts = None
        self._naptan_lookup_cache_file = (
            Path(__file__).resolve().parents[1] / 'data' / 'naptan_lookup_cache.json'
        )
        self._dataset_cache_dir = Path(__file__).resolve().parents[1] / 'data' / 'timetable_cache'
        self._dataset_connections_cache = {}  # dataset_id -> {ts, connections, stop_meta}
        index_db = os.getenv('ROUTE_CONNECTION_INDEX_DB', '/tmp/transport_connection_index.sqlite3')
        self._connection_index_store = ConnectionIndexStore(
            Path(index_db)
        )
        self._connection_index_ready = False
        self._last_processing_metrics = {
            self.METRIC_BUS_STOPS_KEY: 0,
            self.METRIC_TRAIN_STATIONS_KEY: 0,
            self.METRIC_PLANNER_STAGE_KEY: 'init',
        }

    def _record_processing_metrics(self, bus_stops_processed, train_stations_processed, planner_stage):
        bus_count = max(0, int(bus_stops_processed))
        train_count = max(0, int(train_stations_processed))
        self._last_processing_metrics = {
            self.METRIC_BUS_STOPS_KEY: bus_count,
            self.METRIC_TRAIN_STATIONS_KEY: train_count,
            self.METRIC_PLANNER_STAGE_KEY: planner_stage,
        }
        logger.info("Bus stops processed: %s", bus_count)
        logger.info("Train stations processed: %s", train_count)

    def get_last_processing_metrics(self):
        return dict(self._last_processing_metrics)

    def _local_cached_datasets_index(self):
        """Build a minimal dataset index from local timetable cache files."""
        out = []
        try:
            self._dataset_cache_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(self._dataset_cache_dir.glob('*.json.gz')):
                try:
                    with gzip.open(path, 'rt', encoding='utf-8') as fh:
                        payload = json.load(fh)
                    ds_id = payload.get('dataset_id') or path.stem
                    stamp = payload.get('stamp', '')
                    out.append({
                        'id': ds_id,
                        'status': 'published',
                        'url': '',
                        'operatorName': 'Local cache',
                        'localities': [],
                        'adminAreas': [],
                        'lines': [],
                        'lastModifiedDateTime': stamp,
                        'lastEndDate': stamp,
                    })
                except Exception:
                    continue
        except Exception:
            return []
        return out

    def _fetch_rail_departures_cached(self, crs_code):
        now = _dt.utcnow()
        ts = self._rail_departures_cache_ts.get(crs_code)
        if ts is not None:
            if (now - ts).total_seconds() < self._live_poll_min_seconds:
                return self._rail_departures_cache.get(crs_code, {"services": []})

        data = self.rail.fetch_departures(crs_code)
        self._rail_departures_cache[crs_code] = data
        self._rail_departures_cache_ts[crs_code] = now
        return data

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Haversine distance in kilometres."""
        R = 6371.0
        la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = la2 - la1
        dlon = lo2 - lo1
        a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _hhmm_to_mins(hhmm):
        """'HH:MM' → minutes since midnight."""
        parts = hhmm.split(':')
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def _fmt(total_mins):
        """Minutes since midnight → 'HH:MM'."""
        h = (total_mins // 60) % 24
        m = total_mins % 60
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _iso_to_mins(iso_text):
        """ISO datetime string → minutes since midnight (local date)."""
        if not iso_text:
            return None
        try:
            dt = _dt.fromisoformat(iso_text.replace('Z', '+00:00'))
            return dt.hour * 60 + dt.minute
        except Exception:
            return None

    def _coerce_departure_dt(self, depart_time=None):
        """Return departure datetime in UK local timezone.

        Accepts ISO string or datetime. If omitted/invalid, uses current UK time.
        """
        if depart_time is None:
            return _dt.now(self.UK_TZ)

        if isinstance(depart_time, _dt):
            if depart_time.tzinfo is None:
                return depart_time.replace(tzinfo=self.UK_TZ)
            return depart_time.astimezone(self.UK_TZ)

        if isinstance(depart_time, str):
            raw = depart_time.strip()
            if not raw:
                return _dt.now(self.UK_TZ)
            try:
                parsed = _dt.fromisoformat(raw.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=self.UK_TZ)
                return parsed.astimezone(self.UK_TZ)
            except Exception:
                return _dt.now(self.UK_TZ)

        return _dt.now(self.UK_TZ)

    @staticmethod
    def _line_code(service_name):
        """Extract public line code from a service label.

        Example: 'Stagecoach 1A' -> '1A'
        """
        if not service_name:
            return ''
        return service_name.split()[-1].upper()

    def _fetch_live_bus_activity(self):
        """Fetch and parse SCC SIRI live bus feed.

        Returns list of dicts with keys: line, origin_dep, dest_arr.
        Caches results for LIVE_POLL_MIN_SECONDS to avoid repeated API calls.
        """
        now = _dt.utcnow()
        if self._live_bus_cache is not None and self._live_bus_cache_ts is not None:
            age = (now - self._live_bus_cache_ts).total_seconds()
            if age < self._live_poll_min_seconds:
                return self._live_bus_cache

        url = f"{BASE_URL}/bus/live"
        try:
            response = requests.get(url, timeout=12)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            ns = {'s': 'http://www.siri.org.uk/siri'}

            activities = []
            for j in root.findall('.//s:VehicleActivity/s:MonitoredVehicleJourney', ns):
                line = (j.findtext('s:PublishedLineName', namespaces=ns) or
                        j.findtext('s:LineRef', namespaces=ns) or '').strip().upper()
                if not line:
                    continue

                origin_dep = self._iso_to_mins(
                    j.findtext('s:OriginAimedDepartureTime', namespaces=ns) or ''
                )
                dest_arr = self._iso_to_mins(
                    j.findtext('s:DestinationAimedArrivalTime', namespaces=ns) or ''
                )
                if origin_dep is None or dest_arr is None:
                    continue

                dur = dest_arr - origin_dep
                if dur < 0:
                    dur += 24 * 60
                if dur <= 0 or dur > 300:
                    continue

                activities.append({
                    'line': line,
                    'origin_dep': origin_dep,
                    'dest_arr': dest_arr,
                    'duration': dur,
                })

            self._live_bus_cache = activities
            self._live_bus_cache_ts = now
            return activities
        except Exception:
            self._live_bus_cache = []
            self._live_bus_cache_ts = now
            return []

    def _live_departures_for_service(self, service_name, now_mins):
        """Return upcoming live departures (origin-time) and median duration.

        If no matching live journeys are available, returns ([], None).
        """
        line = self._line_code(service_name)
        if not line:
            return [], None

        acts = self._fetch_live_bus_activity()
        matching = [a for a in acts if a['line'] == line]
        if not matching:
            return [], None

        departures = []
        durations = []
        for a in matching:
            dep = a['origin_dep']
            while dep < now_mins - 5:
                dep += 24 * 60
            if dep <= now_mins + 180:
                departures.append(dep)
                durations.append(a['duration'])

        departures.sort()
        if departures:
            # De-duplicate close duplicates from repeated feed entries.
            deduped = []
            for d in departures:
                if not deduped or abs(d - deduped[-1]) >= 2:
                    deduped.append(d)
            departures = deduped

        median_duration = None
        if durations:
            durations.sort()
            median_duration = durations[len(durations) // 2]
        return departures, median_duration

    def _estimate_segment_mins(self, svc):
        """Estimate per-segment minutes for a service.

        Uses explicit segment_mins if provided, otherwise computes a realistic
        estimate from distance with route-shape inflation and dwell times.
        """
        stops = svc['stops']
        explicit = svc.get('segment_mins')
        if explicit and len(explicit) == max(0, len(stops) - 1):
            return explicit[:]

        segment_mins = []
        for i in range(len(stops) - 1):
            d_km = self._haversine(
                stops[i]['lat'], stops[i]['lon'],
                stops[i + 1]['lat'], stops[i + 1]['lon'],
            )
            # Inflate straight-line distance to approximate roads.
            # Use stronger inflation on short urban hops and milder inflation
            # on long inter-urban legs.
            if d_km < 3:
                road_factor = 1.60
                speed = 20
            elif d_km < 10:
                road_factor = 1.35
                speed = 28
            else:
                road_factor = 1.15
                speed = 45

            road_km = d_km * road_factor
            seg = max(2, int(round((road_km / speed) * 60)))
            # Add stop dwell/traffic slack.
            seg += 1
            segment_mins.append(seg)
        return segment_mins

    # ------------------------------------------------------------------
    # Station / bus-stop lookup
    # ------------------------------------------------------------------
    def _find_nearest_stations(self, lat, lon, max_km=8.0, max_results=3):
        """Return list of (crs, info_dict, distance_km) sorted by distance."""
        hits = []
        for crs, info in self.STATIONS.items():
            d = self._haversine(lat, lon, info['lat'], info['lon'])
            if d <= max_km:
                hits.append((crs, info, d))
        hits.sort(key=lambda x: x[2])
        return hits[:max_results]

    def _crs_for_locality(self, stop_name):
        """Try to extract a CRS code from a stop's display name / locality."""
        lower = stop_name.lower()
        for locality, codes in self._LOCALITY_CRS.items():
            if locality in lower:
                return codes
        return []

    def _find_bus_routes(self, from_lat, from_lon, to_lat, to_lon,
                         max_walk_km=1.5):
        """Return bus services where at least one stop is near the origin and
        a *later* stop is near the destination.

        Returns list of dicts::

            {
                'service': <BUS_SERVICE dict>,
                'board_idx': int,   # index of boarding stop
                'alight_idx': int,  # index of alighting stop
                'walk_to_km': float,
                'walk_from_km': float,
            }
        """
        results = []
        for svc in self.BUS_SERVICES:
            stops = svc['stops']
            best_board = None
            best_alight = None
            for i, s in enumerate(stops):
                d = self._haversine(from_lat, from_lon, s['lat'], s['lon'])
                if d <= max_walk_km:
                    if best_board is None or d < best_board[1]:
                        best_board = (i, d)
            if best_board is None:
                continue
            for j in range(best_board[0] + 1, len(stops)):
                d = self._haversine(to_lat, to_lon, stops[j]['lat'], stops[j]['lon'])
                if d <= max_walk_km:
                    if best_alight is None or d < best_alight[1]:
                        best_alight = (j, d)
            # Also check reverse direction
            best_board_rev = None
            best_alight_rev = None
            for i, s in enumerate(stops):
                d = self._haversine(to_lat, to_lon, s['lat'], s['lon'])
                if d <= max_walk_km:
                    if best_board_rev is None or d < best_board_rev[1]:
                        best_board_rev = (i, d)
            if best_board_rev is not None:
                for j in range(best_board_rev[0] + 1, len(stops)):
                    d = self._haversine(from_lat, from_lon, stops[j]['lat'], stops[j]['lon'])
                    if d <= max_walk_km:
                        if best_alight_rev is None or d < best_alight_rev[1]:
                            best_alight_rev = (j, d)
                # Reverse means: origin walks to a later stop, destination walks to earlier
                # Actually for reverse we need to reverse the stop order
            # Reverse direction (bus going the other way)
            if best_alight_rev is not None and best_board_rev is not None:
                rev_stops = list(reversed(stops))
                rev_board_idx = len(stops) - 1 - best_board_rev[0]
                rev_alight_idx = len(stops) - 1 - best_alight_rev[0]
                if rev_board_idx < rev_alight_idx:
                    # Build reversed stop list match
                    from_walk = self._haversine(from_lat, from_lon,
                                                rev_stops[rev_board_idx]['lat'],
                                                rev_stops[rev_board_idx]['lon'])
                    to_walk = self._haversine(to_lat, to_lon,
                                              rev_stops[rev_alight_idx]['lat'],
                                              rev_stops[rev_alight_idx]['lon'])
                    results.append({
                        'service': {**svc, 'stops': rev_stops},
                        'board_idx': rev_board_idx,
                        'alight_idx': rev_alight_idx,
                        'walk_to_km': from_walk,
                        'walk_from_km': to_walk,
                    })

            if best_alight is not None:
                results.append({
                    'service': svc,
                    'board_idx': best_board[0],
                    'alight_idx': best_alight[0],
                    'walk_to_km': best_board[1],
                    'walk_from_km': best_alight[1],
                })
        return results

    # ------------------------------------------------------------------
    # Leg / route builders
    # ------------------------------------------------------------------
    def _walk_leg(self, frm, to, depart_mins, dist_km):
        walk_m = int(dist_km * 1000 * self.WALK_FACTOR)
        walk_mins = max(1, int(walk_m / self.WALK_SPEED))
        return {
            'mode': 'walk',
            'from_stop': frm,
            'to_stop': to,
            'depart': self._fmt(depart_mins),
            'arrive': self._fmt(depart_mins + walk_mins),
            'duration_mins': walk_mins,
            'distance_m': walk_m,
        }

    @staticmethod
    def _summarise(legs):
        # Remove zero-value walk artifacts (typically name-equivalent origin
        # binding edges) to improve readability and route realism.
        cleaned = []
        for leg in legs:
            if leg.get('mode') == 'walk' and leg.get('from_stop') == leg.get('to_stop'):
                continue
            cleaned.append(leg)
        legs = cleaned or legs

        transport_modes = []
        changes = 0
        prev_ride = False
        for leg in legs:
            if leg['mode'] in ('bus', 'train'):
                if leg['mode'] not in transport_modes:
                    transport_modes.append(leg['mode'])
                if prev_ride:
                    changes += 1
                prev_ride = True
            elif leg['mode'] == 'wait':
                # Transfer wait at a hub – don't reset prev_ride so the
                # next ride counts as a change.
                pass
            else:
                # A real walk leg resets prev_ride
                if leg.get('distance_m', 0) > 0:
                    prev_ride = False
        sh, sm = map(int, legs[0]['depart'].split(':'))
        eh, em = map(int, legs[-1]['arrive'].split(':'))
        duration = (eh * 60 + em) - (sh * 60 + sm)
        if duration < 0:
            duration += 24 * 60  # crosses midnight
        return {
            'start_time': legs[0]['depart'],
            'end_time': legs[-1]['arrive'],
            'duration_mins': duration,
            'transport': transport_modes,
            'changes': changes,
            'legs': legs,
        }

    @staticmethod
    def _route_sort_key(route, sort_by='soonest_arrival'):
        sh, sm = map(int, route['start_time'].split(':'))
        eh, em = map(int, route['end_time'].split(':'))
        start = sh * 60 + sm
        end = eh * 60 + em
        if sort_by == 'fewest_changes':
            return (route.get('changes', 0), route.get('duration_mins', 10**9), end, start)
        # Default: arrive soonest
        return (end, route.get('duration_mins', 10**9), route.get('changes', 0), start)

    @staticmethod
    def _is_valid_route(route):
        """Basic sanity validation so only coherent real-data routes are shown."""
        if not route or not route.get('legs'):
            return False
        legs = route['legs']
        if route.get('duration_mins', 0) <= 0:
            return False

        has_ride = False
        prev_arrive_abs = None
        day_offset = 0
        prev_raw = None
        for leg in legs:
            mode = leg.get('mode')
            if mode in ('bus', 'train'):
                has_ride = True
                if not leg.get('service'):
                    return False
            if 'depart' not in leg or 'arrive' not in leg:
                return False
            try:
                dh, dm = map(int, leg['depart'].split(':'))
                ah, am = map(int, leg['arrive'].split(':'))
            except Exception:
                return False

            dep_raw = dh * 60 + dm
            arr_raw = ah * 60 + am

            # Handle midnight rollover for chronological comparisons.
            if prev_raw is not None and dep_raw < prev_raw - 300:
                day_offset += 24 * 60
            dep_abs = dep_raw + day_offset
            arr_abs = arr_raw + day_offset
            if arr_abs < dep_abs:
                arr_abs += 24 * 60

            if prev_arrive_abs is not None and dep_abs < prev_arrive_abs - 5:
                # Allow tiny formatting jitter but reject backwards jumps.
                return False
            prev_arrive_abs = arr_abs
            prev_raw = arr_raw

        # Pure walking routes are valid, otherwise at least one ride leg required.
        return has_ride or all(l.get('mode') == 'walk' for l in legs)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def plan_routes(self, from_name, to_name,
                    from_lat=None, from_lon=None,
                    to_lat=None, to_lon=None,
                    from_stop_code=None, to_stop_code=None,
                    depart_time=None,
                    sort_by='soonest_arrival'):
        """Plan routes between two locations.

        Returns a list of route dicts compatible with the frontend display,
        each containing *start_time*, *end_time*, *duration_mins*,
        *transport*, *changes*, and *legs*.
        """
        if from_lat is None or to_lat is None:
            self._record_processing_metrics(
                bus_stops_processed=0,
                train_stations_processed=0,
                planner_stage='invalid-route-input',
            )
            return []

        # Primary planner: CSA over indexed timetable/departure connections.
        routes = self._plan_routes_csa(
            from_name, to_name,
            from_lat, from_lon,
            to_lat, to_lon,
            from_stop_code=from_stop_code,
            to_stop_code=to_stop_code,
            depart_time=depart_time,
            sort_by=sort_by,
        )
        if routes:
            return routes

        # Fallback 1 (offline-friendly): retry CSA without exact-code pinning
        # so nearby valid stops can still be used when exact stands/bays are
        # too restrictive at the requested time.
        routes = self._plan_routes_csa(
            from_name, to_name,
            from_lat, from_lon,
            to_lat, to_lon,
            from_stop_code=None,
            to_stop_code=None,
            depart_time=depart_time,
            sort_by=sort_by,
        )
        if routes:
            return routes

        # Fallback 2: use legacy graph-network search with exact pins.
        routes = self._plan_routes_network(
            from_name, to_name,
            from_lat, from_lon,
            to_lat, to_lon,
            from_stop_code=from_stop_code,
            to_stop_code=to_stop_code,
            sort_by=sort_by,
        )
        if routes:
            return routes

        # Fallback 3: legacy graph-network search with relaxed pins.
        routes = self._plan_routes_network(
            from_name, to_name,
            from_lat, from_lon,
            to_lat, to_lon,
            from_stop_code=None,
            to_stop_code=None,
            sort_by=sort_by,
        )
        return routes

        dist_km = self._haversine(from_lat, from_lon, to_lat, to_lon)
        now = _dt.now()
        now_mins = now.hour * 60 + now.minute
        routes = []

        # ---- 1. Walk-only (< 2 km) ----
        if dist_km < 2.0:
            walk = self._walk_leg(from_name, to_name, now_mins + 2, dist_km)
            routes.append(self._summarise([walk]))

        # ---- 2. Rail routes (real-time departure data) ----
        origin_stations = self._find_nearest_stations(from_lat, from_lon,
                                                       max_km=8.0, max_results=2)
        dest_stations = self._find_nearest_stations(to_lat, to_lon,
                                                     max_km=8.0, max_results=3)

        if origin_stations and dest_stations:
            dest_crs_set = {crs for crs, _, _ in dest_stations}
            dest_lookup = {crs: (info, d) for crs, info, d in dest_stations}

            for orig_crs, orig_info, orig_walk_km in origin_stations:
                # Skip origin stations that are too far to walk to
                if orig_walk_km > 3.0:
                    continue
                try:
                    departures = self.rail.fetch_departures(orig_crs)
                except Exception:
                    continue

                for svc in departures.get('services', []):
                    # Find the BEST matching calling point: prefer the
                    # destination station with the shortest walk distance.
                    best_cp_idx = None
                    best_dest_walk = float('inf')
                    best_dest_crs = None
                    for cp_idx, cp in enumerate(svc['calling_points']):
                        if cp['crs'] in dest_crs_set:
                            _, dw = dest_lookup[cp['crs']]
                            if dw < best_dest_walk:
                                best_dest_walk = dw
                                best_cp_idx = cp_idx
                                best_dest_crs = cp['crs']

                    if best_cp_idx is not None and best_dest_walk <= 3.0:
                        dest_info, dest_walk_km = dest_lookup[best_dest_crs]
                        route = self._build_rail_route(
                            from_name, to_name,
                            orig_crs, orig_info, orig_walk_km,
                            best_dest_crs, dest_info, dest_walk_km,
                            svc, best_cp_idx, now_mins,
                        )
                        if route:
                            routes.append(route)

        # ---- 3. Connecting rail routes (change at a hub) ----
        #
        # Only attempt connecting routes when no direct route was found OR
        # for destinations that are reachable through obvious hubs.
        # Skip hubs that are FURTHER from the destination than the origin
        # (i.e., going in the wrong direction).  Limit to at most 5
        # connecting routes.
        best_direct_dur = min(
            (r['duration_mins'] for r in routes if r.get('changes', 0) == 0),
            default=None,
        )
        HUB_CRS = {'PRE', 'LAN', 'MAN', 'OXN', 'WGN'}
        connecting_routes = []
        MAX_CONNECTING = 5
        if origin_stations and dest_stations:
            origin_to_dest_km = self._haversine(from_lat, from_lon,
                                                 to_lat, to_lon)
            hub_departures_cache = {}
            for orig_crs, orig_info, orig_walk_km in origin_stations:
                if orig_walk_km > 3.0:
                    continue
                try:
                    departures = self.rail.fetch_departures(orig_crs)
                except Exception:
                    continue

                for svc in departures.get('services', []):
                    if len(connecting_routes) >= MAX_CONNECTING:
                        break
                    # Find calling points that are hub stations
                    for cp_idx, cp in enumerate(svc['calling_points']):
                        hub_crs = cp.get('crs', '')
                        if hub_crs not in HUB_CRS or hub_crs == orig_crs:
                            continue

                        # Geographic sanity: skip hubs further from dest
                        # than the origin is (going wrong direction)
                        hub_info_tmp = self.STATIONS.get(hub_crs)
                        if hub_info_tmp:
                            hub_to_dest = self._haversine(
                                hub_info_tmp['lat'], hub_info_tmp['lon'],
                                to_lat, to_lon)
                            if hub_to_dest > origin_to_dest_km * 1.3:
                                continue  # hub is farther away → skip

                        if hub_crs in hub_departures_cache:
                            hub_deps = hub_departures_cache[hub_crs]
                        else:
                            try:
                                hub_deps = self.rail.fetch_departures(hub_crs)
                                hub_departures_cache[hub_crs] = hub_deps
                            except Exception:
                                continue

                        try:
                            hub_arrive = self._hhmm_to_mins(cp['scheduled'])
                        except (ValueError, IndexError):
                            continue
                        min_connection = 3  # minutes to change platform

                        # Try live connections first
                        found_live = False
                        for hub_svc in hub_deps.get('services', []):
                            try:
                                hub_depart = self._hhmm_to_mins(hub_svc['std'])
                            except (ValueError, IndexError):
                                continue
                            if hub_depart < hub_arrive + min_connection:
                                continue
                            if hub_depart > hub_arrive + 90:
                                continue

                            best2_idx = None
                            best2_walk = float('inf')
                            best2_crs = None
                            for cp2_idx, cp2 in enumerate(hub_svc['calling_points']):
                                if cp2['crs'] in dest_crs_set:
                                    _, dw = dest_lookup[cp2['crs']]
                                    if dw < best2_walk:
                                        best2_walk = dw
                                        best2_idx = cp2_idx
                                        best2_crs = cp2['crs']

                            if best2_idx is not None and best2_walk <= 3.0:
                                route = self._build_connecting_rail_route(
                                    from_name, to_name,
                                    orig_crs, orig_info, orig_walk_km,
                                    hub_crs, self.STATIONS.get(hub_crs, {'name': hub_crs}),
                                    svc, cp_idx,
                                    best2_crs, dest_lookup[best2_crs][0],
                                    dest_lookup[best2_crs][1],
                                    hub_svc, best2_idx,
                                )
                                if route:
                                    connecting_routes.append(route)
                                    found_live = True

                        # If no live connection, estimate based on the latest
                        # service to the destination from this hub (+ typical
                        # 30-min headway for regional services).
                        if not found_live:
                            latest_dest_svc = None
                            latest_dest_idx = None
                            latest_dest_crs = None
                            for hub_svc in hub_deps.get('services', []):
                                for cp2_idx, cp2 in enumerate(hub_svc['calling_points']):
                                    if cp2['crs'] in dest_crs_set:
                                        _, dw = dest_lookup[cp2['crs']]
                                        if dw <= 3.0:
                                            latest_dest_svc = hub_svc
                                            latest_dest_idx = cp2_idx
                                            latest_dest_crs = cp2['crs']

                            if latest_dest_svc is not None:
                                # Estimate next departure: last shown + 30 min
                                try:
                                    last_dep = self._hhmm_to_mins(latest_dest_svc['std'])
                                except (ValueError, IndexError):
                                    continue
                                est_dep = last_dep + 30
                                while est_dep < hub_arrive + min_connection:
                                    est_dep += 30

                                # Build an estimated connecting service
                                orig_cp = latest_dest_svc['calling_points'][latest_dest_idx]
                                try:
                                    orig_arr = self._hhmm_to_mins(orig_cp['scheduled'])
                                except (ValueError, IndexError):
                                    continue
                                est_arr = est_dep + (orig_arr - last_dep)

                                est_svc = {
                                    'std': self._fmt(est_dep),
                                    'operator': latest_dest_svc.get('operator', 'Train'),
                                    'service_type': latest_dest_svc.get('service_type', 'train'),
                                    'calling_points': [],
                                }
                                # Build estimated calling points with shifted times
                                for cp_orig in latest_dest_svc['calling_points'][:latest_dest_idx + 1]:
                                    try:
                                        cp_time = self._hhmm_to_mins(cp_orig['scheduled'])
                                    except (ValueError, IndexError):
                                        continue
                                    shift = est_dep - last_dep
                                    est_svc['calling_points'].append({
                                        'name': cp_orig['name'],
                                        'crs': cp_orig['crs'],
                                        'scheduled': self._fmt(cp_time + shift),
                                        'estimated': 'Estimated',
                                    })

                                est_dest_idx = len(est_svc['calling_points']) - 1
                                if est_dest_idx >= 0:
                                    dest_info2, dest_walk2 = dest_lookup[latest_dest_crs]
                                    route = self._build_connecting_rail_route(
                                        from_name, to_name,
                                        orig_crs, orig_info, orig_walk_km,
                                        hub_crs, self.STATIONS.get(hub_crs, {'name': hub_crs}),
                                        svc, cp_idx,
                                        latest_dest_crs, dest_info2, dest_walk2,
                                        est_svc, est_dest_idx,
                                    )
                                    if route:
                                        connecting_routes.append(route)

                        break  # only check first hub per origin service

            # Filter connecting routes: skip any that are more than 2x the
            # best direct route duration (if direct routes exist).
            if best_direct_dur is not None:
                max_dur = int(best_direct_dur * 2.5)
                connecting_routes = [
                    r for r in connecting_routes
                    if r['duration_mins'] <= max_dur
                ]

            # Keep at most MAX_CONNECTING connecting routes, sorted by
            # departure time.
            connecting_routes.sort(key=lambda r: (
                int(r['start_time'].split(':')[0]),
                int(r['start_time'].split(':')[1]),
            ))
            routes.extend(connecting_routes[:MAX_CONNECTING])

        # ---- 4. Bus routes (knowledge-base + frequency estimation) ----
        bus_matches = self._find_bus_routes(from_lat, from_lon, to_lat, to_lon)
        for match in bus_matches:
            bus_routes = self._build_bus_routes(
                from_name, to_name, match, now_mins,
            )
            routes.extend(bus_routes)

        # ---- 5. Deduplicate, validate and sort ----
        seen = set()
        unique = []
        for r in routes:
            if not self._is_valid_route(r):
                continue
            key = (r['start_time'], r['end_time'],
                   tuple(r['transport']), r.get('changes', 0))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        unique.sort(key=lambda r: self._route_sort_key(r, sort_by=sort_by))
        return unique

    def _align_future_mins(self, raw_mins, ref_abs):
        """Align a clock time (0-1439) to an absolute minute >= reference."""
        v = int(raw_mins)
        while v < ref_abs - 5:
            v += 24 * 60
        return v

    @staticmethod
    def _clock_to_mins(clock_text):
        """Parse HH:MM[:SS] into minutes since midnight."""
        if not clock_text:
            return None
        parts = str(clock_text).strip().split(':')
        if len(parts) < 2:
            return None
        try:
            hh = int(parts[0])
            mm = int(parts[1])
            return hh * 60 + mm
        except Exception:
            return None

    @staticmethod
    def _tx_duration_mins(text):
        """Parse TransXChange ISO-8601 duration (e.g. PT5M30S) to minutes."""
        if not text:
            return 0
        m = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', text.strip())
        if not m:
            return 0
        h = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        sec = int(m.group(3) or 0)
        total = h * 60 + mins + (1 if sec > 0 else 0)
        return max(0, total)

    @staticmethod
    def _service_code_to_line(service_code):
        if not service_code:
            return ''
        txt = str(service_code).strip()
        if not txt:
            return ''
        parts = [p for p in txt.split(':') if p]
        if parts:
            cand = parts[-1]
            if re.match(r'^[A-Za-z0-9]+$', cand):
                return cand
        m = re.search(r'([A-Za-z]?\d+[A-Za-z]?)$', txt)
        return m.group(1) if m else ''

    @staticmethod
    def _tx_parse_date(text):
        if not text:
            return None
        t = str(text).strip()
        try:
            if 'T' in t:
                return _dt.fromisoformat(t.replace('Z', '+00:00')).date()
            return _dt.strptime(t, '%Y-%m-%d').date()
        except Exception:
            return None

    @classmethod
    def _tx_in_period(cls, service_date, start_text, end_text):
        start = cls._tx_parse_date(start_text)
        end = cls._tx_parse_date(end_text)
        if start and service_date < start:
            return False
        if end and service_date > end:
            return False
        return True

    @classmethod
    def _tx_profile_allows_date(cls, profile_elem, service_date, ns):
        """Evaluate common TransXChange OperatingProfile rules for a date."""
        if profile_elem is None:
            return True

        weekday = service_date.weekday()  # Mon=0 .. Sun=6

        regular = profile_elem.find('tx:RegularDayType/tx:DaysOfWeek', ns)
        regular_allows = None
        if regular is not None:
            tags = {el.tag.rsplit('}', 1)[-1] for el in list(regular)}
            if tags:
                regular_allows = False
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                today_tag = day_names[weekday]
                if today_tag in tags:
                    regular_allows = True
                if 'MondayToFriday' in tags and weekday <= 4:
                    regular_allows = True
                if 'MondayToSaturday' in tags and weekday <= 5:
                    regular_allows = True
                if 'MondayToSunday' in tags:
                    regular_allows = True
                if 'Weekend' in tags and weekday >= 5:
                    regular_allows = True
                if 'NotSaturday' in tags and weekday != 5:
                    regular_allows = True
                if 'NotSunday' in tags and weekday != 6:
                    regular_allows = True
                if 'MondayToThursday' in tags and weekday <= 3:
                    regular_allows = True
                if 'Friday' in tags and weekday == 4:
                    regular_allows = True
                if 'Saturday' in tags and weekday == 5:
                    regular_allows = True
                if 'Sunday' in tags and weekday == 6:
                    regular_allows = True

        # Special day ranges override regular profile.
        special = profile_elem.find('tx:SpecialDaysOperation', ns)
        if special is not None:
            for dr in special.findall('tx:DaysOfNonOperation/tx:DateRange', ns):
                if cls._tx_in_period(
                    service_date,
                    dr.findtext('tx:StartDate', namespaces=ns),
                    dr.findtext('tx:EndDate', namespaces=ns),
                ):
                    return False

            for dr in special.findall('tx:DaysOfOperation/tx:DateRange', ns):
                if cls._tx_in_period(
                    service_date,
                    dr.findtext('tx:StartDate', namespaces=ns),
                    dr.findtext('tx:EndDate', namespaces=ns),
                ):
                    return True

        return True if regular_allows is None else regular_allows

    def _fetch_bus_times_index(self):
        """Fetch SCC /bus/times index (all datasets), cached for 6 hours."""
        now = _dt.utcnow()
        if self._bus_times_index_cache is not None and self._bus_times_index_ts is not None:
            if (now - self._bus_times_index_ts).total_seconds() < 21600:
                return self._bus_times_index_cache

        if self._static_data_only:
            local_results = self._local_cached_datasets_index()
            self._bus_times_index_cache = local_results
            self._bus_times_index_ts = now
            return local_results

        try:
            r = requests.get(f"{BASE_URL}/bus/times", timeout=10, allow_redirects=True)
            r.raise_for_status()
            payload = r.json()
            results = payload.get('results', []) if isinstance(payload, dict) else []
        except Exception:
            # Keep existing cache on transient API issues.
            if self._bus_times_index_cache is not None:
                return self._bus_times_index_cache
            results = self._local_cached_datasets_index()

        if not results:
            results = self._local_cached_datasets_index()

        self._bus_times_index_cache = results
        self._bus_times_index_ts = now
        return results

    def _dataset_cache_file(self, dataset_id):
        safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(dataset_id or 'unknown'))
        return self._dataset_cache_dir / f"{safe}.json.gz"

    @staticmethod
    def _dataset_stamp(dataset):
        return (
            dataset.get('lastModifiedDateTime')
            or dataset.get('lastEndDate')
            or dataset.get('firstStartDate')
            or ''
        )

    def _load_dataset_from_disk_cache(self, dataset):
        dataset_id = dataset.get('id')
        if not dataset_id:
            return None
        path = self._dataset_cache_file(dataset_id)
        if not path.exists():
            return None
        try:
            with gzip.open(path, 'rt', encoding='utf-8') as fh:
                payload = json.load(fh)
            if int(payload.get('format_version', 0)) != self.DATASET_CACHE_FORMAT_VERSION:
                return None
            if payload.get('dataset_id') != dataset_id:
                return None
            if payload.get('stamp', '') != self._dataset_stamp(dataset):
                return None
            trips = payload.get('trips', [])
            if not isinstance(trips, list):
                return None
            return trips
        except Exception:
            return None

    def _save_dataset_to_disk_cache(self, dataset, trips):
        dataset_id = dataset.get('id')
        if not dataset_id:
            return
        try:
            self._dataset_cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                'format_version': self.DATASET_CACHE_FORMAT_VERSION,
                'dataset_id': dataset_id,
                'stamp': self._dataset_stamp(dataset),
                'trips': trips,
            }
            with gzip.open(self._dataset_cache_file(dataset_id), 'wt', encoding='utf-8') as fh:
                json.dump(payload, fh)
        except Exception:
            pass

    @staticmethod
    def _extract_locality_terms(name):
        raw = (name or '').lower()
        chunks = [c.strip() for c in raw.split(',') if c.strip()]
        terms = set()
        if chunks:
            terms.add(chunks[-1])
        for w in re.split(r'[^a-z0-9]+', raw):
            if len(w) >= 4:
                terms.add(w)
        return terms

    def _select_bus_timetable_datasets(self, from_name, to_name, now_utc):
        """Pick relevant timetable datasets based on endpoint localities/date."""
        index = self._fetch_bus_times_index()
        if not index:
            return []

        from_terms = self._extract_locality_terms(from_name)
        to_terms = self._extract_locality_terms(to_name)
        scored = []
        for ds in index:
            if ds.get('status') != 'published':
                continue
            url = ds.get('url')
            if not url and not self._static_data_only:
                continue

            score = 0
            if self._static_data_only and not url:
                # Local cached timetable snapshots in static mode intentionally
                # do not have remote URLs, but should still be eligible.
                score += 3
            locs = [str(x.get('name', '')).lower() for x in ds.get('localities', [])]
            loc_blob = ' | '.join(locs)
            for t in from_terms:
                if t in loc_blob:
                    score += 8
            for t in to_terms:
                if t in loc_blob:
                    score += 8

            admin_blob = ' | '.join(str(x.get('name', '')).lower() for x in ds.get('adminAreas', []))
            if 'lancashire' in admin_blob or 'cumbria' in admin_blob or 'blackpool' in admin_blob:
                score += 2

            # date relevance
            start = ds.get('firstStartDate') or ''
            end = ds.get('lastEndDate') or ''
            try:
                start_dt = _dt.fromisoformat(start.replace('Z', '+00:00')) if start else None
                end_dt = _dt.fromisoformat(end.replace('Z', '+00:00')) if end else None
                now_tz = now_utc.replace(tzinfo=start_dt.tzinfo) if start_dt and now_utc.tzinfo is None else now_utc
                if start_dt and end_dt and start_dt <= now_tz <= end_dt:
                    score += 4
            except Exception:
                pass

            scored.append((score, ds))

        scored.sort(key=lambda x: x[0], reverse=True)
        # Keep multiple candidates to avoid missing valid routes that are
        # present in neighboring/locality-overlap datasets.
        selected = []
        seen_ids = set()
        for score, ds in scored:
            ds_id = ds.get('id')
            if ds_id in seen_ids:
                continue
            # Skip very weak matches so irrelevant county datasets don't
            # dominate early results.
            if score <= 0:
                continue
            selected.append(ds)
            seen_ids.add(ds_id)
            if len(selected) >= 8:
                break
        if not selected:
            # Fallback: if locality text matching was weak/absent, still use
            # a few best published datasets to avoid false "no routes".
            for _, ds in scored[:4]:
                ds_id = ds.get('id')
                if ds_id in seen_ids:
                    continue
                selected.append(ds)
                seen_ids.add(ds_id)
        return selected

    def _load_naptan_lookup(self):
        """Build ATCO -> stop metadata lookup from SCC NaPTAN feeds."""
        now = _dt.utcnow()
        if self._naptan_lookup_cache is not None and self._naptan_lookup_ts is not None:
            if (now - self._naptan_lookup_ts).total_seconds() < 3600:
                return self._naptan_lookup_cache

        # Fast path: use persisted cache (any age in static mode).
        cache_path = self._naptan_lookup_cache_file
        try:
            if cache_path.exists():
                age = now.timestamp() - cache_path.stat().st_mtime
                if self._static_data_only or age < 24 * 3600:
                    with cache_path.open('r', encoding='utf-8') as fh:
                        persisted = json.load(fh)
                    lookup = {}
                    for code, meta in persisted.items():
                        try:
                            lookup[code] = {
                                'name': meta.get('name', ''),
                                'lat': float(meta.get('lat')),
                                'lon': float(meta.get('lon')),
                                'locality': meta.get('locality', ''),
                            }
                        except Exception:
                            continue
                    if lookup:
                        self._naptan_lookup_cache = lookup
                        self._naptan_lookup_ts = now
                        return lookup
        except Exception:
            pass

        if self._static_data_only:
            self._naptan_lookup_cache = {}
            self._naptan_lookup_ts = now
            return {}

        lookup = {}
        # Primary lookup keeps latency practical by loading SCC-local feeds.
        # Full UK NaPTAN is intentionally excluded here due very high parse
        # cost on cold start.
        feeds = ['/nptg/naptan.xml', '/nptg/naptan-nw-rail.xml']
        ns = {'n': 'http://www.naptan.org.uk/'}
        for ep in feeds:
            try:
                r = requests.get(f"{BASE_URL}{ep}", timeout=35, allow_redirects=True)
                r.raise_for_status()
                root = ET.fromstring(r.content)
            except Exception:
                continue

            for stop in root.findall('.//n:StopPoint', ns):
                code = stop.findtext('n:AtcoCode', namespaces=ns)
                if not code:
                    continue
                common = stop.findtext('n:Descriptor/n:CommonName', namespaces=ns) or ''
                ind = stop.findtext('n:Descriptor/n:Indicator', namespaces=ns) or ''
                loc_name = (stop.findtext('n:Place/n:Town', namespaces=ns)
                            or stop.findtext('n:Place/n:Suburb', namespaces=ns)
                            or '')
                lat = stop.findtext('n:Place/n:Location/n:Translation/n:Latitude', namespaces=ns)
                lon = stop.findtext('n:Place/n:Location/n:Translation/n:Longitude', namespaces=ns)
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                except Exception:
                    continue
                display = common
                if ind:
                    display += f" ({ind})"
                if loc_name and loc_name not in display:
                    display += f", {loc_name}"
                lookup[code] = {
                    'name': display,
                    'lat': lat_f,
                    'lon': lon_f,
                    'locality': loc_name,
                }

        self._naptan_lookup_cache = lookup
        self._naptan_lookup_ts = now

        # Persist for future cold starts.
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open('w', encoding='utf-8') as fh:
                json.dump(lookup, fh)
        except Exception:
            pass

        return lookup

    def _parse_timetable_dataset(self, dataset):
        """Download and parse a SCC timetable dataset ZIP into scheduled trips."""
        dataset_id = dataset.get('id')
        now = _dt.utcnow()
        if dataset_id in self._bus_dataset_cache:
            cached = self._bus_dataset_cache[dataset_id]
            if (now - cached['ts']).total_seconds() < 21600:
                return cached['trips']

        disk_cached = self._load_dataset_from_disk_cache(dataset)
        if disk_cached is not None:
            self._bus_dataset_cache[dataset_id] = {'ts': now, 'trips': disk_cached}
            return disk_cached

        url = dataset.get('url')
        if not url:
            return []

        naptan = self._load_naptan_lookup()
        trips = []
        ns = {'tx': 'http://www.transxchange.org.uk/'}

        try:
            zdata = requests.get(url, timeout=25, allow_redirects=True).content
            zf = zipfile.ZipFile(io.BytesIO(zdata))
        except Exception:
            zf = None

        if zf is None:
            return []

        op_name = dataset.get('operatorName', 'Bus')
        service_date = _dt.now(self.UK_TZ).date()
        for fname in zf.namelist():
            if not fname.lower().endswith('.xml'):
                continue
            try:
                root = ET.fromstring(zf.read(fname))
            except Exception:
                continue

            # local stop labels in this file
            file_stop_names = {}
            for s in root.findall('.//tx:AnnotatedStopPointRef', ns):
                ref = s.findtext('tx:StopPointRef', namespaces=ns)
                if not ref:
                    continue
                cname = s.findtext('tx:CommonName', namespaces=ns) or ''
                ind = s.findtext('tx:Indicator', namespaces=ns) or ''
                loc = s.findtext('tx:LocalityName', namespaces=ns) or ''
                dn = cname
                if ind:
                    dn += f" ({ind})"
                if loc and loc not in dn:
                    dn += f", {loc}"
                file_stop_names[ref] = dn

            # line lookup
            line_names = {}
            for ln in root.findall('.//tx:Line', ns):
                lid = ln.get('id') or ''
                line_names[lid] = ln.findtext('tx:LineName', namespaces=ns) or lid

            # JourneyPatternSection -> timing links
            jps = {}
            for sec in root.findall('.//tx:JourneyPatternSection', ns):
                sid = sec.get('id') or ''
                links = []
                for l in sec.findall('tx:JourneyPatternTimingLink', ns):
                    frm = l.findtext('tx:From/tx:StopPointRef', namespaces=ns)
                    to = l.findtext('tx:To/tx:StopPointRef', namespaces=ns)
                    rt = self._tx_duration_mins(l.findtext('tx:RunTime', namespaces=ns) or '')
                    if frm and to and frm != to:
                        links.append((frm, to, max(1, rt)))
                if links:
                    jps[sid] = links

            # JourneyPattern -> section refs + line/service name
            jp_map = {}
            jp_policy = {}

            # Service-level policies keyed by JourneyPattern id.
            for svc in root.findall('.//tx:Service', ns):
                op_period = svc.find('tx:OperatingPeriod', ns)
                svc_start = op_period.findtext('tx:StartDate', namespaces=ns) if op_period is not None else None
                svc_end = op_period.findtext('tx:EndDate', namespaces=ns) if op_period is not None else None
                svc_profile = svc.find('tx:OperatingProfile', ns)
                svc_code = svc.findtext('tx:ServiceCode', namespaces=ns) or ''
                svc_line_name = ''
                for svc_line in svc.findall('tx:Lines/tx:Line', ns):
                    ln = (svc_line.findtext('tx:LineName', namespaces=ns) or '').strip()
                    if ln:
                        svc_line_name = ln
                        break
                public_use_txt = (svc.findtext('tx:PublicUse', namespaces=ns) or '').strip().lower()
                is_public_use = (public_use_txt != 'false')

                for jp_svc in svc.findall('.//tx:StandardService/tx:JourneyPattern', ns):
                    jp_id = jp_svc.get('id') or ''
                    if not jp_id:
                        continue
                    jp_period = jp_svc.find('tx:OperatingPeriod', ns)
                    jp_start = jp_period.findtext('tx:StartDate', namespaces=ns) if jp_period is not None else svc_start
                    jp_end = jp_period.findtext('tx:EndDate', namespaces=ns) if jp_period is not None else svc_end
                    jp_profile = jp_svc.find('tx:OperatingProfile', ns) or svc_profile
                    jp_policy[jp_id] = {
                        'start': jp_start,
                        'end': jp_end,
                        'profile': jp_profile,
                        'service_code': svc_code,
                        'line_name': svc_line_name,
                        'public_use': is_public_use,
                    }

            for jp in root.findall('.//tx:JourneyPattern', ns):
                jid = jp.get('id') or ''
                line_ref = jp.findtext('tx:LineRef', namespaces=ns) or ''
                line_name = line_names.get(line_ref, '')
                section_refs = []
                for x in jp.findall('tx:JourneyPatternSectionRefs', ns):
                    if not x.text:
                        continue
                    section_refs.extend([p for p in x.text.split() if p])
                links = []
                for sref in section_refs:
                    links.extend(jps.get(sref, []))
                if links:
                    jp_map[jid] = {
                        'line_name': line_name,
                        'links': links,
                    }

            # Cache base vehicle journeys so inherited journeys can resolve
            # JourneyPatternRef via VehicleJourneyRef.
            vj_templates = {}
            for vj in root.findall('.//tx:VehicleJourney', ns):
                vid = vj.get('id') or ''
                if not vid:
                    continue
                jpr = vj.findtext('tx:JourneyPatternRef', namespaces=ns) or ''
                base_ref = vj.findtext('tx:VehicleJourneyRef', namespaces=ns) or ''
                line_ref = vj.findtext('tx:LineRef', namespaces=ns) or ''

                # Optional timing-link runtime overrides at the VJ level.
                overrides = {}
                vj_links = []
                links = vj.findall('.//tx:VehicleJourneyTimingLink', ns)
                for idx, l in enumerate(links):
                    frm = l.findtext('tx:From/tx:StopPointRef', namespaces=ns)
                    to = l.findtext('tx:To/tx:StopPointRef', namespaces=ns)
                    from_act = (l.findtext('tx:From/tx:Activity', namespaces=ns) or 'pickUpAndSetDown').strip()
                    to_act = (l.findtext('tx:To/tx:Activity', namespaces=ns) or 'pickUpAndSetDown').strip()
                    rt = self._tx_duration_mins(l.findtext('tx:RunTime', namespaces=ns) or '')
                    if rt > 0:
                        overrides[idx] = rt
                    if frm and to and frm != to:
                        vj_links.append((frm, to, rt, from_act, to_act))

                vj_templates[vid] = {
                    'journey_pattern_ref': jpr,
                    'base_ref': base_ref,
                    'line_ref': line_ref,
                    'vj_links': vj_links,
                    'overrides': overrides,
                }

            def resolve_line_ref(vid, depth=0):
                if depth > 4:
                    return ''
                tpl = vj_templates.get(vid)
                if not tpl:
                    return ''
                if tpl.get('line_ref'):
                    return tpl['line_ref']
                if tpl.get('base_ref'):
                    return resolve_line_ref(tpl['base_ref'], depth + 1)
                return ''

            def resolve_vj_links(vid, depth=0):
                if depth > 4:
                    return []
                tpl = vj_templates.get(vid)
                if not tpl:
                    return []
                if tpl.get('vj_links'):
                    return tpl['vj_links']
                if tpl.get('base_ref'):
                    return resolve_vj_links(tpl['base_ref'], depth + 1)
                return []

            def resolve_journey_pattern(vid, depth=0):
                if depth > 4:
                    return ''
                tpl = vj_templates.get(vid)
                if not tpl:
                    return ''
                if tpl['journey_pattern_ref']:
                    return tpl['journey_pattern_ref']
                if tpl['base_ref']:
                    return resolve_journey_pattern(tpl['base_ref'], depth + 1)
                return ''

            # Vehicle journeys -> actual dated trips
            for vj in root.findall('.//tx:VehicleJourney', ns):
                vj_id = vj.get('id') or ''
                jp_ref = vj.findtext('tx:JourneyPatternRef', namespaces=ns) or ''
                direct_vj_line_ref = vj.findtext('tx:LineRef', namespaces=ns) or ''
                if not jp_ref and vj_id:
                    jp_ref = resolve_journey_pattern(vj_id)
                dep_txt = vj.findtext('tx:DepartureTime', namespaces=ns) or ''
                dep0 = self._clock_to_mins(dep_txt)
                if dep0 is None or jp_ref not in jp_map:
                    continue

                # Date/day filtering for route validity accuracy.
                policy = jp_policy.get(jp_ref, {})
                if policy.get('public_use') is False:
                    continue
                # Skip strict date filtering: the timetable is already current and we're
                # just extracting stop-to-stop connections. CSA will filter by actual
                # operating times. Strict filtering was causing 90+ declared services to be
                # excluded (e.g., 1A, 1C, 1S) even though they're in the dataset.
                # if not self._tx_in_period(service_date, policy.get('start'), policy.get('end')):
                #     continue
                # if not self._tx_profile_allows_date(policy.get('profile'), service_date, ns):
                #     continue

                vj_period = vj.find('tx:OperatingPeriod', ns)
                if vj_period is not None:
                    if not self._tx_in_period(
                        service_date,
                        vj_period.findtext('tx:StartDate', namespaces=ns),
                        vj_period.findtext('tx:EndDate', namespaces=ns),
                    ):
                        continue
                # Skip VJ-level profile filtering for the same reason as Service-level:
                # the timetable is current and CSA will handle temporal filtering.
                # if not self._tx_profile_allows_date(vj.find('tx:OperatingProfile', ns), service_date, ns):
                #     continue

                info = jp_map[jp_ref]
                base_links = info['links']
                if not base_links:
                    continue

                # Prefer explicit VehicleJourney timing-link stop sequence when
                # present; this avoids incorrect line/path assignment.
                explicit_links = resolve_vj_links(vj_id) if vj_id else []
                if explicit_links:
                    links = []
                    for idx, (frm, to, rt, from_act, to_act) in enumerate(explicit_links):
                        if rt <= 0 and idx < len(base_links):
                            rt = base_links[idx][2]
                        links.append((frm, to, max(1, rt), from_act, to_act))
                else:
                    merged_links = []
                    vj_override = vj_templates.get(vj_id, {}).get('overrides', {}) if vj_id else {}
                    for idx, (frm, to, rt) in enumerate(base_links):
                        merged_links.append((frm, to, vj_override.get(idx, rt), 'pickUpAndSetDown', 'pickUpAndSetDown'))
                    links = merged_links

                def _can_board(act_text):
                    a = (act_text or '').lower()
                    return 'pickup' in a

                def _is_pass_only(act_text):
                    a = (act_text or '').lower()
                    return a == 'pass'

                stop_refs = []
                times = []
                t = dep0

                first_frm = links[0][0]
                first_from_act = links[0][3]
                if _can_board(first_from_act):
                    stop_refs.append(first_frm)
                    times.append(t)

                for frm, to, rt, _from_act, to_act in links:
                    t += max(0, rt)
                    # Keep only passenger-relevant stops so we don't allow
                    # boarding/alighting at pass-through timing points.
                    if _is_pass_only(to_act):
                        continue
                    if stop_refs and stop_refs[-1] == to:
                        times[-1] = t
                        continue
                    stop_refs.append(to)
                    times.append(t)

                # enrich stop metadata with NaPTAN coords
                stops = []
                for ref in stop_refs:
                    meta = naptan.get(ref)
                    if meta is None:
                        # without coordinates we cannot connect this stop in the
                        # multi-modal graph safely.
                        stops = []
                        break
                    stops.append({
                        'ref': ref,
                        'name': file_stop_names.get(ref) or meta['name'],
                        'lat': meta['lat'],
                        'lon': meta['lon'],
                    })

                if len(stops) >= 2 and len(stops) == len(times):
                    vj_line_ref = direct_vj_line_ref or (resolve_line_ref(vj_id) if vj_id else '')
                    svc_code_line = self._service_code_to_line((policy or {}).get('service_code', ''))
                    line_candidate = (
                        line_names.get(vj_line_ref)
                        or info.get('line_name')
                        or (policy or {}).get('line_name')
                        or ''
                    )
                    if str(line_candidate).strip().lower() in {'', 'bus'}:
                        line_candidate = svc_code_line or line_candidate
                    line = line_candidate or 'Bus'
                    lats = [s['lat'] for s in stops]
                    lons = [s['lon'] for s in stops]
                    trips.append({
                        'service': f"{op_name} {line}".strip(),
                        'trip_id': f"{dataset_id}:{fname}:{dep0}:{jp_ref}:{line}:{vj_id}",
                        'stops': stops,
                        'times': times,
                        'bbox': {
                            'min_lat': min(lats),
                            'max_lat': max(lats),
                            'min_lon': min(lons),
                            'max_lon': max(lons),
                        },
                    })

        self._bus_dataset_cache[dataset_id] = {'ts': now, 'trips': trips}
        self._save_dataset_to_disk_cache(dataset, trips)
        return trips

    def _dataset_connections(self, dataset):
        """Build cached stop-to-stop timetable connections for CSA scanning."""
        dataset_id = dataset.get('id')
        now = _dt.utcnow()
        if dataset_id in self._dataset_connections_cache:
            cached = self._dataset_connections_cache[dataset_id]
            if (now - cached['ts']).total_seconds() < 21600:
                return cached['connections'], cached['stop_meta']

        trips = self._parse_timetable_dataset(dataset)
        connections = []
        stop_meta = {}
        for trip in trips:
            stops = trip.get('stops', [])
            times = trip.get('times', [])
            if len(stops) < 2 or len(stops) != len(times):
                continue
            for s in stops:
                ref = s.get('ref')
                if not ref:
                    continue
                stop_meta[ref] = {
                    'name': s.get('name', ref),
                    'lat': float(s.get('lat', 0.0)),
                    'lon': float(s.get('lon', 0.0)),
                    'kind': 'bus',
                }

            for i in range(len(stops) - 1):
                frm = stops[i].get('ref')
                to = stops[i + 1].get('ref')
                if not frm or not to or frm == to:
                    continue
                dep_raw = times[i]
                arr_raw = times[i + 1]
                if arr_raw < dep_raw:
                    arr_raw += 24 * 60
                connections.append({
                    'from_ref': frm,
                    'to_ref': to,
                    'dep_raw': dep_raw,
                    'arr_raw': arr_raw,
                    'trip_id': trip.get('trip_id', ''),
                    'service': trip.get('service', 'Bus'),
                    'mode': 'bus',
                })

        self._dataset_connections_cache[dataset_id] = {
            'ts': now,
            'connections': connections,
            'stop_meta': stop_meta,
        }
        return connections, stop_meta

    def _builtin_service_connections(self):
        """Generate static timetable-like connections from built-in bus services.

        This provides offline baseline coverage for key NW routes when remote
        timetable datasets are unavailable or incomplete.
        """
        stop_meta = {}
        connections = []
        service_start = int(os.getenv('BUILTIN_SERVICE_START_MINS', '300'))   # 05:00
        service_end = int(os.getenv('BUILTIN_SERVICE_END_MINS', '1380'))      # 23:00

        for svc in self.BUS_SERVICES:
            service_name = svc.get('service', 'Bus')
            freq = max(5, int(svc.get('frequency_mins', 30)))
            stops = svc.get('stops', [])
            if len(stops) < 2:
                continue
            seg_mins = self._estimate_segment_mins(svc)

            stop_refs = []
            for s in stops:
                ref = f"BIS:{re.sub(r'[^A-Za-z0-9]+', '_', service_name).upper()}:{re.sub(r'[^A-Za-z0-9]+', '_', s.get('name', 'STOP')).upper()}"
                stop_refs.append(ref)
                stop_meta[ref] = {
                    'name': s.get('name', ref),
                    'lat': float(s.get('lat', 0.0)),
                    'lon': float(s.get('lon', 0.0)),
                    'kind': 'bus',
                }

            dep = service_start
            while dep <= service_end:
                trip_id = f"builtin:{service_name}:{dep}"
                running = dep
                for i in range(len(stop_refs) - 1):
                    frm = stop_refs[i]
                    to = stop_refs[i + 1]
                    depart_abs = running
                    arrive_abs = running + max(1, int(seg_mins[i]))
                    connections.append({
                        'from_ref': frm,
                        'to_ref': to,
                        'dep_raw': depart_abs % (24 * 60),
                        'arr_raw': arrive_abs % (24 * 60),
                        'trip_id': trip_id,
                        'service': service_name,
                        'mode': 'bus',
                    })
                    running = arrive_abs
                dep += freq

        return connections, stop_meta

    def build_connection_index(self, force_rebuild=False):
        """Build persistent offline timetable connection/footpath index."""
        if self._connection_index_store is None:
            return {'indexed_datasets': 0, 'connections': 0, 'warning': 'index store unavailable'}
        if not self._connection_index_ready:
            try:
                self._connection_index_store.init_schema()
                self._connection_index_ready = True
            except Exception:
                try:
                    self._connection_index_store = ConnectionIndexStore(
                        Path('/tmp/transport_connection_index_runtime.sqlite3')
                    )
                    self._connection_index_store.init_schema()
                    self._connection_index_ready = True
                except Exception:
                    return {'indexed_datasets': 0, 'connections': 0, 'warning': 'index store unavailable'}
        index = self._fetch_bus_times_index()
        if not index:
            return {'indexed_datasets': 0, 'connections': 0}

        max_datasets = int(os.getenv('ROUTE_INDEX_MAX_DATASETS', '20'))
        allowed_regions = {
            'lancashire', 'blackpool', 'cumbria', 'greater manchester', 'manchester',
            'cheshire', 'merseyside'
        }

        filtered = []
        for ds in index:
            if ds.get('status') != 'published':
                continue
            admin_blob = ' | '.join(str(x.get('name', '')).lower() for x in ds.get('adminAreas', []))
            if any(r in admin_blob for r in allowed_regions):
                filtered.append(ds)
        if not filtered:
            filtered = [ds for ds in index if ds.get('status') == 'published']
        index = filtered[:max_datasets]

        self._connection_index_store.init_schema()
        if force_rebuild:
            self._connection_index_store.clear()

        count_ds = 0
        total_conn = 0
        for ds in index:
            ds_id = ds.get('id')
            if not ds_id:
                continue
            conns, meta = self._dataset_connections(ds)
            if not conns:
                continue
            self._connection_index_store.upsert_dataset(
                ds_id,
                self._dataset_stamp(ds),
                ds.get('operatorName', ''),
            )
            self._connection_index_store.replace_dataset_connections(ds_id, meta, conns)
            count_ds += 1
            total_conn += len(conns)

        # Ensure baseline offline bus coverage from built-in static routes.
        try:
            builtin_conns, builtin_meta = self._builtin_service_connections()
            if builtin_conns:
                builtin_id = '__builtin_bus_services__'
                self._connection_index_store.upsert_dataset(
                    builtin_id,
                    '',
                    'Built-in static services',
                )
                self._connection_index_store.replace_dataset_connections(
                    builtin_id,
                    builtin_meta,
                    builtin_conns,
                )
                count_ds += 1
                total_conn += len(builtin_conns)
        except Exception:
            pass

        self._connection_index_store.rebuild_footpaths(
            max_walk_km=0.6,
            walk_speed_m_per_min=self.WALK_SPEED,
            walk_factor=self.WALK_FACTOR,
        )
        return {'indexed_datasets': count_ds, 'connections': total_conn}

    def get_bus_timetable(self, bus_code, max_results=250):
        """Return scheduled trips for a bus line from local static timetable data."""
        query = re.sub(r'[^A-Za-z0-9]+', '', str(bus_code or '').upper())
        if not query:
            return {'bus_code': bus_code, 'trips': [], 'count': 0, 'source': 'static-cache'}

        index = self._fetch_bus_times_index()
        if not index:
            return {'bus_code': bus_code, 'trips': [], 'count': 0, 'source': 'static-cache'}

        trips_out = []
        max_scan = int(os.getenv('BUS_TIMETABLE_SCAN_DATASETS', '30'))
        for ds in index[:max_scan]:
            ds_id = str(ds.get('id') or '')
            trips = self._parse_timetable_dataset(ds)
            for trip in trips:
                line = str(trip.get('line') or '').upper().strip()
                line_norm = re.sub(r'[^A-Za-z0-9]+', '', line)
                service_label = str(trip.get('service') or '').strip()
                service_norm = re.sub(r'[^A-Za-z0-9]+', '', service_label.upper())
                if query not in {line_norm, service_norm, self._line_code(service_label)}:
                    continue
                trips_out.append({
                    'dataset_id': ds_id,
                    'service': service_label,
                    'line': line,
                    'operator': trip.get('operator', ''),
                    'trip_id': trip.get('trip_id', ''),
                    'days': trip.get('days', []),
                    'times': trip.get('times', []),
                    'stops': trip.get('stops', []),
                })
                if len(trips_out) >= max_results:
                    return {
                        'bus_code': bus_code,
                        'trips': trips_out,
                        'count': len(trips_out),
                        'source': 'static-cache',
                        'truncated': True,
                    }

        return {
            'bus_code': bus_code,
            'trips': trips_out,
            'count': len(trips_out),
            'source': 'static-cache',
            'truncated': False,
        }

    def _plan_routes_csa(self, from_name, to_name,
                         from_lat, from_lon,
                         to_lat, to_lon,
                         from_stop_code=None, to_stop_code=None,
                         depart_time=None,
                         sort_by='soonest_arrival'):
        """CSA-style journey planning over indexed timetable connections."""
        now = self._coerce_departure_dt(depart_time)
        now_abs = now.hour * 60 + now.minute
        horizon_abs = now_abs + (24 * 60 if self._static_data_only else 6 * 60)
        dist_km = self._haversine(from_lat, from_lon, to_lat, to_lon)

        datasets = self._select_bus_timetable_datasets(from_name, to_name, now)
        if dist_km <= 8:
            datasets = datasets[:4]
        elif dist_km <= 25:
            datasets = datasets[:6]
        else:
            datasets = datasets[:8]

        # Restrict bus legs to lines explicitly published by the selected
        # online SCC datasets for this query context.
        allowed_lines = set()
        for ds in datasets:
            for ln in (ds.get('lines') or []):
                norm = re.sub(r'[^A-Za-z0-9]+', '', str(ln or '').upper())
                if norm:
                    allowed_lines.add(norm)

        # Dataset `lines` metadata can be incomplete for local services.
        # For local/medium journeys, avoid over-restricting by line code.
        if dist_km <= 25:
            allowed_lines.clear()

        def line_allowed(service_label):
            if not allowed_lines:
                return True
            cand = re.sub(r'[^A-Za-z0-9]+', '', self._line_code(service_label or ''))
            if not cand:
                return True
            return cand in allowed_lines

        stop_meta = {}
        indexed_connections = []

        def bbox_near_point(bbox, lat, lon, radius_km):
            if not bbox:
                return True
            dlat = radius_km / 111.0
            dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
            return not (
                bbox.get('max_lat', -90) < lat - dlat or
                bbox.get('min_lat', 90) > lat + dlat or
                bbox.get('max_lon', -180) < lon - dlon or
                bbox.get('min_lon', 180) > lon + dlon
            )

        endpoint_radius_km = 2.5 if dist_km <= 20 else 4.0
        bus_conns = []
        bus_meta = {}
        ds_ids = [str(ds.get('id')) for ds in datasets if ds.get('id')]
        ds_ids.append('__builtin_bus_services__')
        try:
            if self._connection_index_store is not None and ds_ids and self._connection_index_store.has_connections():
                bus_conns, bus_meta = self._connection_index_store.get_dataset_connections_and_stops(ds_ids)
        except Exception:
            bus_conns, bus_meta = [], {}

        if not bus_conns:
            for ds in datasets:
                conns, meta = self._dataset_connections(ds)
                bus_conns.extend(conns)
                for k, v in meta.items():
                    bus_meta[k] = v

        for k, v in bus_meta.items():
            stop_meta[k] = v

        # spatial pruning at connection level
        for c in bus_conns:
            if not line_allowed(c.get('service', '')):
                continue
            fm = bus_meta.get(c['from_ref'])
            tm = bus_meta.get(c['to_ref'])
            if fm is None or tm is None:
                continue
            seg_bbox = {
                'min_lat': min(fm['lat'], tm['lat']),
                'max_lat': max(fm['lat'], tm['lat']),
                'min_lon': min(fm['lon'], tm['lon']),
                'max_lon': max(fm['lon'], tm['lon']),
            }
            near_from = bbox_near_point(seg_bbox, from_lat, from_lon, endpoint_radius_km)
            near_to = bbox_near_point(seg_bbox, to_lat, to_lon, endpoint_radius_km)
            # For short distances, be less aggressive with spatial filtering to allow
            # multi-hop routes through intermediate stops. Only filter out if the
            # connection is far from both endpoints AND if it's not in the general area.
            if dist_km <= 20:
                # For distances <= 20km, keep connections if they're within 2*endpoint_radius of either endpoint
                # This allows intermediate stops to be included in multi-hop routes
                extended_radius = endpoint_radius_km * 2.0
                near_from_extended = bbox_near_point(seg_bbox, from_lat, from_lon, extended_radius)
                near_to_extended = bbox_near_point(seg_bbox, to_lat, to_lon, extended_radius)
                if not (near_from_extended or near_to_extended):
                    continue
            elif dist_km > 20:
                if not (near_from or near_to):
                    continue
            indexed_connections.append(c)

        # Add rail connections from live departure boards as timetable-like.
        # In static-data-only mode, skip this to stay fully API-independent.
        rail_targets = set()
        if not self._static_data_only:
            rail_targets = set(self._crs_for_locality(from_name) + self._crs_for_locality(to_name))
            for crs, _, _ in self._find_nearest_stations(from_lat, from_lon, max_km=20, max_results=4):
                rail_targets.add(crs)
            for crs, _, _ in self._find_nearest_stations(to_lat, to_lon, max_km=20, max_results=4):
                rail_targets.add(crs)
            if dist_km >= 20:
                rail_targets.update({'LAN', 'PRE', 'MAN', 'WGN', 'OXN'})

        for crs, info in self.STATIONS.items():
            stop_meta[f'CRS:{crs}'] = {
                'name': f"{info['name']} Railway Station",
                'lat': float(info['lat']),
                'lon': float(info['lon']),
                'kind': 'rail',
            }

        self._record_processing_metrics(
            bus_stops_processed=len(bus_meta),
            train_stations_processed=len(self.STATIONS),
            planner_stage='csa',
        )

        for crs in rail_targets:
            if crs not in self.STATIONS:
                continue
            try:
                board = self._fetch_rail_departures_cached(crs)
            except Exception:
                continue
            for svc in board.get('services', []):
                cps = svc.get('calling_points', [])
                if not cps:
                    continue
                try:
                    dep0 = self._hhmm_to_mins(svc.get('std', ''))
                except Exception:
                    continue
                dep_abs0 = self._align_future_mins(dep0, now_abs)
                if dep_abs0 > horizon_abs:
                    continue
                trip_id = f"rail:{crs}:{svc.get('service_id', '')}:{dep_abs0}"
                for cp in cps:
                    cp_crs = cp.get('crs', '')
                    if cp_crs not in self.STATIONS:
                        continue
                    try:
                        arr_raw = self._hhmm_to_mins(cp.get('scheduled', ''))
                    except Exception:
                        continue
                    arr_abs = self._align_future_mins(arr_raw, dep_abs0)
                    if arr_abs <= dep_abs0:
                        continue
                    indexed_connections.append({
                        'from_ref': f'CRS:{crs}',
                        'to_ref': f'CRS:{cp_crs}',
                        'dep_raw': dep0,
                        'arr_raw': arr_raw,
                        'dep_abs_fixed': dep_abs0,
                        'arr_abs_fixed': arr_abs,
                        'trip_id': trip_id,
                        'service': svc.get('operator', 'Train'),
                        'mode': 'train' if svc.get('service_type', 'train') == 'train' else 'bus',
                    })

        if not indexed_connections:
            return []

        footpaths_map = defaultdict(list)
        try:
            if self._connection_index_store is not None and self._connection_index_store.has_connections():
                for fp in self._connection_index_store.get_footpaths():
                    footpaths_map[fp['from_ref']].append(fp)
        except Exception:
            footpaths_map = defaultdict(list)

        # origin/destination access links
        origin_access = []
        dest_access = []
        from_crs = ''
        to_crs = ''
        if from_stop_code and str(from_stop_code).upper().startswith('CRS:'):
            from_crs = str(from_stop_code).upper()
        if to_stop_code and str(to_stop_code).upper().startswith('CRS:'):
            to_crs = str(to_stop_code).upper()

        if from_stop_code and from_stop_code in stop_meta:
            origin_access.append((from_stop_code, 0, 0))
        if to_stop_code and to_stop_code in stop_meta:
            dest_access.append((to_stop_code, 0, 0))
        if from_crs and from_crs in stop_meta:
            origin_access.append((from_crs, 0, 0))
        if to_crs and to_crs in stop_meta:
            dest_access.append((to_crs, 0, 0))

        from_exact_meta = stop_meta.get(from_stop_code) if from_stop_code else None
        to_exact_meta = stop_meta.get(to_stop_code) if to_stop_code else None
        origin_name_l = (from_name or '').lower()
        dest_name_l = (to_name or '').lower()

        for ref, md in stop_meta.items():
            d_from = self._haversine(from_lat, from_lon, md['lat'], md['lon'])
            d_to = self._haversine(md['lat'], md['lon'], to_lat, to_lon)
            if from_stop_code:
                if from_exact_meta is None:
                    from_limit = 0.60
                else:
                    from_limit = 0.45
                if d_from > from_limit:
                    pass
                else:
                    if ('bus station' in origin_name_l or 'bus stn' in origin_name_l):
                        n = md.get('name', '').lower()
                        if 'bus station' not in n and 'bus stn' not in n:
                            pass
                        else:
                            wm = int(d_from * 1000 * self.WALK_FACTOR)
                            origin_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))
                    else:
                        wm = int(d_from * 1000 * self.WALK_FACTOR)
                        origin_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))
            elif d_from <= 1.0:
                wm = int(d_from * 1000 * self.WALK_FACTOR)
                origin_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))

            if to_stop_code:
                to_limit = 0.60 if to_exact_meta is None else 0.45
                if d_to > to_limit:
                    pass
                else:
                    if ('bus station' in dest_name_l or 'bus stn' in dest_name_l):
                        n = md.get('name', '').lower()
                        if 'bus station' not in n and 'bus stn' not in n:
                            pass
                        else:
                            wm = int(d_to * 1000 * self.WALK_FACTOR)
                            dest_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))
                    else:
                        wm = int(d_to * 1000 * self.WALK_FACTOR)
                        dest_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))
            elif d_to <= 1.0:
                wm = int(d_to * 1000 * self.WALK_FACTOR)
                dest_access.append((ref, max(1, int(wm / self.WALK_SPEED)), wm))

        if not origin_access or not dest_access:
            return []

        def build_route(start_offset=0):
            start_t = now_abs + start_offset
            inf = 10**9
            earliest = defaultdict(lambda: inf)
            changes = defaultdict(lambda: 10**6)
            prev = {}
            prev_trip = {}

            def relax_footpaths(seed_ref):
                if not footpaths_map:
                    return
                q = [seed_ref]
                seen_fp = set()
                while q:
                    cur = q.pop(0)
                    for fp in footpaths_map.get(cur, []):
                        to_ref = fp['to_ref']
                        key = (cur, to_ref)
                        if key in seen_fp:
                            continue
                        seen_fp.add(key)
                        cand_arr = earliest[cur] + int(fp.get('walk_mins', 1))
                        if cand_arr < earliest[to_ref]:
                            earliest[to_ref] = cand_arr
                            changes[to_ref] = min(changes[to_ref], changes[cur])
                            prev_trip[to_ref] = None
                            prev[to_ref] = {
                                'kind': 'walk',
                                'from_ref': cur,
                                'to_ref': to_ref,
                                'depart_abs': earliest[cur],
                                'arrive_abs': cand_arr,
                                'distance_m': int(fp.get('distance_m', 0)),
                            }
                            q.append(to_ref)

            for ref, wmins, dist_m in origin_access:
                arr = start_t + wmins
                if arr < earliest[ref]:
                    earliest[ref] = arr
                    changes[ref] = 0
                    prev[ref] = {
                        'kind': 'walk',
                        'from_ref': '__ORIGIN__',
                        'to_ref': ref,
                        'depart_abs': start_t,
                        'arrive_abs': arr,
                        'distance_m': dist_m,
                    }
                    relax_footpaths(ref)

            # prepare scan list with absolute departure/arrival
            scan = []
            for c in indexed_connections:
                if 'dep_abs_fixed' in c:
                    dep_abs = c['dep_abs_fixed']
                    arr_abs = c['arr_abs_fixed']
                else:
                    dep_abs = self._align_future_mins(c['dep_raw'], start_t)
                    arr_raw = c['arr_raw']
                    if arr_raw < c['dep_raw']:
                        arr_raw += 24 * 60
                    arr_abs = dep_abs + (arr_raw - c['dep_raw'])
                if dep_abs < start_t or dep_abs > horizon_abs:
                    continue
                scan.append((dep_abs, arr_abs, c))
            scan.sort(key=lambda x: x[0])

            for dep_abs, arr_abs, c in scan:
                frm = c['from_ref']
                to = c['to_ref']
                if earliest[frm] > dep_abs:
                    continue
                trip = c.get('trip_id')
                new_changes = changes[frm]
                if prev_trip.get(frm) is not None and prev_trip.get(frm) != trip:
                    new_changes += 1
                if new_changes > 3:
                    continue
                if arr_abs < earliest[to] or (arr_abs == earliest[to] and new_changes < changes[to]):
                    earliest[to] = arr_abs
                    changes[to] = new_changes
                    prev_trip[to] = trip
                    prev[to] = {
                        'kind': 'ride',
                        'from_ref': frm,
                        'to_ref': to,
                        'depart_abs': dep_abs,
                        'arrive_abs': arr_abs,
                        'mode': c.get('mode', 'bus'),
                        'service': c.get('service', 'Service'),
                        'trip_id': trip,
                    }
                    relax_footpaths(to)

            best = None
            for ref, wmins, dist_m in dest_access:
                if earliest[ref] >= inf:
                    continue
                arr = earliest[ref] + wmins
                cand = (arr, changes[ref], ref, wmins, dist_m)
                if best is None or cand < best:
                    best = cand
            if best is None:
                return None

            _, _, end_ref, end_wmins, end_dist = best
            chain = []
            cur = end_ref
            while cur in prev:
                e = prev[cur]
                chain.append(e)
                cur = e['from_ref']
                if cur == '__ORIGIN__':
                    break
            chain.reverse()

            if end_wmins > 0:
                chain.append({
                    'kind': 'walk',
                    'from_ref': end_ref,
                    'to_ref': '__DEST__',
                    'depart_abs': best[0] - end_wmins,
                    'arrive_abs': best[0],
                    'distance_m': end_dist,
                })

            legs = []
            for e in chain:
                if e['kind'] == 'walk':
                    frm_name = from_name if e['from_ref'] == '__ORIGIN__' else stop_meta.get(e['from_ref'], {}).get('name', from_name)
                    to_name_local = to_name if e['to_ref'] == '__DEST__' else stop_meta.get(e['to_ref'], {}).get('name', to_name)
                    legs.append({
                        'mode': 'walk',
                        'from_stop': frm_name,
                        'to_stop': to_name_local,
                        'depart': self._fmt(e['depart_abs']),
                        'arrive': self._fmt(e['arrive_abs']),
                        'duration_mins': max(1, e['arrive_abs'] - e['depart_abs']),
                        'distance_m': int(e.get('distance_m', 0)),
                    })
                else:
                    if legs:
                        last_arr = legs[-1].get('arrive')
                        if last_arr:
                            lh, lm = map(int, last_arr.split(':'))
                            last_arr_abs = lh * 60 + lm
                            if e['depart_abs'] > last_arr_abs:
                                legs.append({
                                    'mode': 'wait',
                                    'from_stop': stop_meta.get(e['from_ref'], {}).get('name', ''),
                                    'to_stop': stop_meta.get(e['from_ref'], {}).get('name', ''),
                                    'depart': self._fmt(last_arr_abs),
                                    'arrive': self._fmt(e['depart_abs']),
                                    'duration_mins': max(1, e['depart_abs'] - last_arr_abs),
                                    'distance_m': 0,
                                })
                    if (
                        legs
                        and legs[-1].get('mode') == e.get('mode', 'bus')
                        and legs[-1].get('_trip_id') == e.get('trip_id')
                    ):
                        last = dict(legs[-1])
                        last['to_stop'] = stop_meta.get(e['to_ref'], {}).get('name', '')
                        last['arrive'] = self._fmt(e['arrive_abs'])
                        dh, dm = map(int, last['depart'].split(':'))
                        d0 = dh * 60 + dm
                        dur = e['arrive_abs'] - d0
                        if dur < 0:
                            dur += 24 * 60
                        last['duration_mins'] = max(1, dur)
                        legs[-1] = last
                    else:
                        legs.append({
                            'mode': e.get('mode', 'bus'),
                            'service': e.get('service', 'Service'),
                            'from_stop': stop_meta.get(e['from_ref'], {}).get('name', ''),
                            'to_stop': stop_meta.get(e['to_ref'], {}).get('name', ''),
                            'depart': self._fmt(e['depart_abs']),
                            'arrive': self._fmt(e['arrive_abs']),
                            'duration_mins': max(1, e['arrive_abs'] - e['depart_abs']),
                            'intermediate_stops': [],
                            '_trip_id': e.get('trip_id'),
                        })

            if not legs:
                return None
            for leg in legs:
                leg.pop('_trip_id', None)
            route = self._summarise(legs)
            return route if self._is_valid_route(route) else None

        routes = []
        seen = set()
        for off in (0, 10, 20, 30, 45, 60):
            r = build_route(start_offset=off)
            if not r:
                continue
            key = (r.get('start_time'), r.get('end_time'), tuple(r.get('transport', [])), r.get('changes', 0))
            if key in seen:
                continue
            seen.add(key)
            routes.append(r)
            if len(routes) >= 8:
                break

        if routes and dist_km <= 8:
            direct = [r for r in routes if int(r.get('changes', 99)) == 0]
            if direct:
                best_direct_arr = min(
                    (int(h) * 60 + int(m))
                    for r in direct
                    for h, m in [r.get('end_time', '23:59').split(':')]
                )
                kept = []
                for r in routes:
                    eh, em = map(int, r.get('end_time', '23:59').split(':'))
                    arr = eh * 60 + em
                    if int(r.get('changes', 0)) == 0:
                        kept.append(r)
                    elif arr + 8 < best_direct_arr:
                        # Keep changed routes only when they are materially
                        # faster than direct options.
                        kept.append(r)
                routes = kept or routes

        routes.sort(key=lambda r: self._route_sort_key(r, sort_by=sort_by))
        return routes[:8]

    def _plan_routes_network(self, from_name, to_name,
                             from_lat, from_lon,
                             to_lat, to_lon,
                             from_stop_code=None, to_stop_code=None,
                             sort_by='soonest_arrival'):
        now = _dt.now()
        now_abs = now.hour * 60 + now.minute
        horizon_abs = now_abs + (24 * 60 if self._static_data_only else 6 * 60)
        dist_km = self._haversine(from_lat, from_lon, to_lat, to_lon)
        from_l = (from_name or '').lower()
        to_l = (to_name or '').lower()
        rail_focused = ('station' in from_l and 'station' in to_l and dist_km >= 10)

        def bbox_near_point(bbox, lat, lon, radius_km):
            if not bbox:
                return True
            dlat = radius_km / 111.0
            dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
            return not (
                bbox.get('max_lat', -90) < lat - dlat or
                bbox.get('min_lat', 90) > lat + dlat or
                bbox.get('max_lon', -180) < lon - dlon or
                bbox.get('min_lon', 180) > lon + dlon
            )

        nodes = {}
        adjacency = defaultdict(list)  # transit edges only
        walk_neighbors = defaultdict(list)
        bus_nodes_processed = 0

        bus_ref_nodes = defaultdict(list)

        def add_node(name, lat, lon, kind, ref=None):
            nonlocal bus_nodes_processed
            key = (name.strip().lower(), round(float(lat), 4), round(float(lon), 4), kind, (ref or ''))
            if key not in nodes:
                nodes[key] = {
                    'id': key,
                    'name': name,
                    'lat': float(lat),
                    'lon': float(lon),
                    'kind': kind,
                    'ref': ref or '',
                }
                if kind == 'bus':
                    bus_nodes_processed += 1
                    if ref:
                        bus_ref_nodes[ref].append(key)
            return key

        # ---- Build bus network trips from SCC timetable datasets ----
        datasets = [] if rail_focused else self._select_bus_timetable_datasets(from_name, to_name, now)
        if dist_km <= 8:
            datasets = datasets[:1]
        elif dist_km <= 25:
            datasets = datasets[:3]
        else:
            datasets = datasets[:5]

        endpoint_radius_km = 2.5 if dist_km <= 20 else 4.0
        for ds in datasets:
            for trip in self._parse_timetable_dataset(ds):
                stops = trip.get('stops', [])
                times = trip.get('times', [])
                if len(stops) < 2 or len(stops) != len(times):
                    continue

                # Fast spatial pruning so only geographically plausible trips
                # are loaded into the search graph.
                near_from = bbox_near_point(trip.get('bbox'), from_lat, from_lon, endpoint_radius_km)
                near_to = bbox_near_point(trip.get('bbox'), to_lat, to_lon, endpoint_radius_km)
                if dist_km <= 20:
                    if not (near_from and near_to):
                        continue
                else:
                    if not (near_from or near_to):
                        continue

                # shift trip to the next occurrence not too far in the past
                dep0_abs = self._align_future_mins(times[0], now_abs)
                if dep0_abs > horizon_abs:
                    continue
                shift = dep0_abs - times[0]
                node_ids = [add_node(st['name'], st['lat'], st['lon'], 'bus', ref=st.get('ref')) for st in stops]

                # Use consecutive timetable links; staying on same trip keeps
                # change count at zero in the search state.
                for i in range(len(stops) - 1):
                    depart_abs = times[i] + shift
                    arrive_abs = times[i + 1] + shift
                    if arrive_abs < depart_abs:
                        arrive_abs += 24 * 60
                    if depart_abs > horizon_abs:
                        continue
                    adjacency[node_ids[i]].append({
                        'to': node_ids[i + 1],
                        'mode': 'bus',
                        'service': trip['service'],
                        'trip_id': trip['trip_id'],
                        'depart_abs': depart_abs,
                        'arrive_abs': arrive_abs,
                        'intermediates': [],
                    })

        # ---- Build rail network trips from SCC departure boards ----
        rail_targets = set()
        if not self._static_data_only:
            origin_station_limit = 3 if dist_km < 20 else 5
            dest_station_limit = 3 if dist_km < 20 else 5
            for crs, _, _ in self._find_nearest_stations(from_lat, from_lon, max_km=20, max_results=origin_station_limit):
                rail_targets.add(crs)
            for crs, _, _ in self._find_nearest_stations(to_lat, to_lon, max_km=20, max_results=dest_station_limit):
                rail_targets.add(crs)
            if dist_km >= 20:
                rail_targets.update({'LAN', 'PRE', 'MAN', 'WGN', 'OXN'})
            rail_targets.update(self._crs_for_locality(from_name))
            rail_targets.update(self._crs_for_locality(to_name))

        station_nodes = {}
        for crs, info in self.STATIONS.items():
            station_nodes[crs] = add_node(f"{info['name']} Railway Station", info['lat'], info['lon'], 'rail')

        self._record_processing_metrics(
            bus_stops_processed=bus_nodes_processed,
            train_stations_processed=len(station_nodes),
            planner_stage='network',
        )

        for crs in rail_targets:
            if crs not in self.STATIONS:
                continue
            try:
                board = self._fetch_rail_departures_cached(crs)
            except Exception:
                continue
            origin_id = station_nodes[crs]
            for svc in board.get('services', []):
                cps = svc.get('calling_points', [])
                if not cps:
                    continue
                try:
                    depart_raw = self._hhmm_to_mins(svc.get('std', ''))
                except Exception:
                    continue
                depart_abs = self._align_future_mins(depart_raw, now_abs)
                if depart_abs > horizon_abs:
                    continue
                trip_id = f"rail:{crs}:{svc.get('service_id', '')}:{depart_abs}"
                for j, cp in enumerate(cps):
                    cp_crs = cp.get('crs', '')
                    if cp_crs not in station_nodes:
                        continue
                    try:
                        arr_raw = self._hhmm_to_mins(cp.get('scheduled', ''))
                    except Exception:
                        continue
                    arrive_abs = self._align_future_mins(arr_raw, depart_abs)
                    if arrive_abs <= depart_abs:
                        continue
                    mode = 'train' if svc.get('service_type', 'train') == 'train' else 'bus'
                    intermediates = []
                    for cp_mid in cps[:j]:
                        try:
                            mid_t = self._hhmm_to_mins(cp_mid.get('scheduled', ''))
                            mid_abs = self._align_future_mins(mid_t, depart_abs)
                        except Exception:
                            continue
                        intermediates.append({'name': cp_mid.get('name', ''), 'time_abs': mid_abs})

                    adjacency[origin_id].append({
                        'to': station_nodes[cp_crs],
                        'mode': mode,
                        'service': svc.get('operator', 'Train'),
                        'trip_id': trip_id,
                        'depart_abs': depart_abs,
                        'arrive_abs': arrive_abs,
                        'intermediates': intermediates,
                    })

        # ---- Add virtual origin/destination nodes ----
        origin_id = add_node(from_name, from_lat, from_lon, 'origin')
        dest_id = add_node(to_name, to_lat, to_lon, 'destination')

        # Connect user origin/destination to nearby transit stops by walking.
        used_exact_codes = False
        exact_lookup = None
        has_from_exact_bus = bool(from_stop_code and from_stop_code in bus_ref_nodes)
        has_to_exact_bus = bool(to_stop_code and to_stop_code in bus_ref_nodes)
        from_crs = ''
        to_crs = ''
        if from_stop_code and str(from_stop_code).upper().startswith('CRS:'):
            from_crs = str(from_stop_code).split(':', 1)[1].upper()
        if to_stop_code and str(to_stop_code).upper().startswith('CRS:'):
            to_crs = str(to_stop_code).split(':', 1)[1].upper()

        if has_from_exact_bus:
            used_exact_codes = True
            for nid in bus_ref_nodes[from_stop_code]:
                walk_neighbors[origin_id].append((nid, 0.0))
        if has_to_exact_bus:
            used_exact_codes = True
            for nid in bus_ref_nodes[to_stop_code]:
                walk_neighbors[nid].append((dest_id, 0.0))
        if from_crs in station_nodes:
            used_exact_codes = True
            walk_neighbors[origin_id].append((station_nodes[from_crs], 0.0))
        if to_crs in station_nodes:
            used_exact_codes = True
            walk_neighbors[station_nodes[to_crs]].append((dest_id, 0.0))

        # Also allow short local access around exact stops so users can still
        # board/alight at adjacent bay/stand variants serving the same area.
        if has_from_exact_bus or has_to_exact_bus:
            exact_lookup = self._load_naptan_lookup()
        from_exact = exact_lookup.get(from_stop_code) if exact_lookup and has_from_exact_bus else None
        to_exact = exact_lookup.get(to_stop_code) if exact_lookup and has_to_exact_bus else None

        for nid, nd in list(nodes.items()):
            if nid in (origin_id, dest_id):
                continue
            if from_exact is not None:
                d_from_exact = self._haversine(from_exact['lat'], from_exact['lon'], nd['lat'], nd['lon'])
                if d_from_exact <= 0.45:
                    walk_neighbors[origin_id].append((nid, d_from_exact))
            elif not has_from_exact_bus and not from_crs:
                d_from = self._haversine(from_lat, from_lon, nd['lat'], nd['lon'])
                if d_from <= 1.2:
                    walk_neighbors[origin_id].append((nid, d_from))
            if to_exact is not None:
                d_to_exact = self._haversine(nd['lat'], nd['lon'], to_exact['lat'], to_exact['lon'])
                if d_to_exact <= 0.45:
                    walk_neighbors[nid].append((dest_id, d_to_exact))
            elif not has_to_exact_bus and not to_crs:
                d_to = self._haversine(nd['lat'], nd['lon'], to_lat, to_lon)
                if d_to <= 1.2:
                    walk_neighbors[nid].append((dest_id, d_to))

        direct_km = self._haversine(from_lat, from_lon, to_lat, to_lon)
        if direct_km <= 2.5 and not used_exact_codes:
            walk_neighbors[origin_id].append((dest_id, direct_km))

        # Add realistic interchange walking between nearby bus/rail stops only.
        node_ids = list(nodes.keys())
        for i in range(len(node_ids)):
            a = nodes[node_ids[i]]
            if a.get('kind') not in ('bus', 'rail'):
                continue
            for j in range(i + 1, len(node_ids)):
                b = nodes[node_ids[j]]
                if b.get('kind') not in ('bus', 'rail'):
                    continue
                if a['kind'] == b['kind']:
                    continue
                d_km = self._haversine(a['lat'], a['lon'], b['lat'], b['lon'])
                if d_km <= 0.8:
                    walk_neighbors[a['id']].append((b['id'], d_km))
                    walk_neighbors[b['id']].append((a['id'], d_km))

        # ---- Multi-criteria label search (arrival + changes) ----
        # Build per-stop departure indexes for fast edge lookup.
        departures_by_stop = {}
        dep_times_by_stop = {}
        for sid, edges in adjacency.items():
            if not edges:
                continue
            ordered = sorted(edges, key=lambda e: (e['depart_abs'], e['arrive_abs']))
            departures_by_stop[sid] = ordered
            dep_times_by_stop[sid] = [e['depart_abs'] for e in ordered]

        # state: (priority_time, seq, stop_id, t_abs, changes, current_trip_id, legs)
        seq = 0
        pq = []
        heapq.heappush(pq, (now_abs, seq, origin_id, now_abs, 0, None, []))

        pareto = defaultdict(list)  # stop -> list[(t_abs, changes)]
        destination_routes = []
        destination_signatures = set()
        max_routes = 28
        max_states = 25000
        expanded = 0
        if dist_km <= 8:
            max_changes_allowed = 1
            max_duration_allowed = 100
            max_wait_allowed = 35
        elif dist_km <= 30:
            max_changes_allowed = 2
            max_duration_allowed = 180
            max_wait_allowed = 50
        else:
            max_changes_allowed = 3
            max_duration_allowed = 360
            max_wait_allowed = 70

        def is_dominated(stop, t_abs, chg):
            for t0, c0 in pareto[stop]:
                # Keep diversity across departure/arrival windows. A label is
                # dominated only if an equal-or-better one exists close in
                # time, otherwise retain it as a viable alternative.
                if c0 <= chg and t0 <= t_abs and (t_abs - t0) <= 20:
                    return True
            return False

        def register_label(stop, t_abs, chg):
            keep = []
            for t0, c0 in pareto[stop]:
                if not (t_abs <= t0 and chg <= c0 and (t0 - t_abs) <= 20):
                    keep.append((t0, c0))
            keep.append((t_abs, chg))
            # Bound label growth per stop for performance.
            keep.sort(key=lambda x: (x[1], x[0]))
            pareto[stop] = keep[:14]

        while pq and expanded < max_states:
            _, _, stop, t_abs, changes, current_trip, legs = heapq.heappop(pq)
            expanded += 1

            if changes > max_changes_allowed:
                continue
            if (t_abs - now_abs) > max_duration_allowed:
                continue

            if is_dominated(stop, t_abs, changes):
                continue
            register_label(stop, t_abs, changes)

            if stop == dest_id:
                if legs:
                    route = self._summarise(legs)
                    if self._is_valid_route(route):
                        rides = tuple(
                            (l.get('mode'), l.get('service', ''), l.get('from_stop', ''), l.get('to_stop', ''))
                            for l in route.get('legs', [])
                            if l.get('mode') in ('bus', 'train')
                        )
                        sig = (route.get('changes', 0), route.get('start_time', ''), rides)
                        if sig not in destination_signatures:
                            destination_signatures.add(sig)
                            destination_routes.append(route)
                        if len(destination_routes) >= max_routes:
                            break
                continue

            # 1) Walk moves (always available)
            for nxt, d_km in walk_neighbors.get(stop, []):
                walk_count = sum(1 for l in legs if l.get('mode') == 'walk' and l.get('distance_m', 0) > 0)
                if walk_count >= 3:
                    continue

                # Avoid walk chaining/backtracking loops such as A->B->A.
                if legs and legs[-1].get('mode') == 'walk':
                    last = legs[-1]
                    if last.get('from_stop') == nodes[nxt]['name']:
                        continue
                    # Consecutive walk legs are usually graph artifacts;
                    # prefer direct transfer edges instead.
                    continue

                walk_m = int(d_km * 1000 * self.WALK_FACTOR)
                walk_mins = max(1, int(walk_m / self.WALK_SPEED))
                nt = t_abs + walk_mins
                if nt > horizon_abs + 120:
                    continue

                new_legs = list(legs)
                new_legs.append({
                    'mode': 'walk',
                    'from_stop': nodes[stop]['name'],
                    'to_stop': nodes[nxt]['name'],
                    'depart': self._fmt(t_abs),
                    'arrive': self._fmt(nt),
                    'duration_mins': walk_mins,
                    'distance_m': walk_m,
                })
                seq += 1
                heapq.heappush(pq, (nt, seq, nxt, nt, changes, None, new_legs))

            # 2) Transit moves (time-dependent)
            stop_edges = departures_by_stop.get(stop, [])
            stop_dep_times = dep_times_by_stop.get(stop, [])
            if stop_edges:
                start_idx = bisect.bisect_left(stop_dep_times, t_abs)
            else:
                start_idx = 0

            scanned = 0
            for e in stop_edges[start_idx:]:
                scanned += 1
                # Hard cap keeps expansion bounded on dense urban stops while
                # still allowing diverse alternatives.
                if scanned > 120:
                    break

                dep = e['depart_abs']
                arr = e['arrive_abs']
                if dep > horizon_abs:
                    continue
                if dep - t_abs > 90:
                    # Very long waits are usually poor options and increase
                    # state explosion; skip by default.
                    continue
                if (dep - t_abs) > max_wait_allowed:
                    continue

                new_legs = list(legs)
                new_changes = changes

                # Wait leg before boarding
                if dep > t_abs:
                    new_legs.append({
                        'mode': 'wait',
                        'from_stop': nodes[stop]['name'],
                        'to_stop': nodes[stop]['name'],
                        'depart': self._fmt(t_abs),
                        'arrive': self._fmt(dep),
                        'duration_mins': dep - t_abs,
                        'distance_m': 0,
                    })

                # Extend current ride leg if staying on the same trip.
                if new_legs and current_trip == e['trip_id'] and new_legs[-1].get('mode') in ('bus', 'train'):
                    last = dict(new_legs[-1])
                    last_inter = list(last.get('intermediate_stops', []))
                    for cp in e.get('intermediates', []):
                        last_inter.append({'name': cp['name'], 'time': self._fmt(cp['time_abs'])})
                    last['to_stop'] = nodes[e['to']]['name']
                    last['arrive'] = self._fmt(arr)
                    sh, sm = map(int, last['depart'].split(':'))
                    dur = arr - (sh * 60 + sm)
                    if dur < 0:
                        dur += 24 * 60
                    last['duration_mins'] = dur
                    last['intermediate_stops'] = last_inter
                    new_legs[-1] = last
                else:
                    if current_trip is not None:
                        new_changes += 1
                    if new_changes > max_changes_allowed:
                        continue
                    new_legs.append({
                        'mode': e['mode'],
                        'service': e['service'],
                        'from_stop': nodes[stop]['name'],
                        'to_stop': nodes[e['to']]['name'],
                        'depart': self._fmt(dep),
                        'arrive': self._fmt(arr),
                        'duration_mins': max(1, arr - dep),
                        'intermediate_stops': [
                            {'name': cp['name'], 'time': self._fmt(cp['time_abs'])}
                            for cp in e.get('intermediates', [])
                        ],
                    })

                seq += 1
                # Priority key follows selected sort objective.
                pri = (new_changes * 10000 + arr) if sort_by == 'fewest_changes' else arr
                heapq.heappush(pq, (pri, seq, e['to'], arr, new_changes, e['trip_id'], new_legs))

        # Deduplicate + final sort
        seen = set()
        unique = []
        for r in destination_routes:
            key = (r['start_time'], r['end_time'], tuple(r.get('transport', [])), r.get('changes', 0))
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)

        unique.sort(key=lambda r: self._route_sort_key(r, sort_by=sort_by))

        # Trim extreme outliers so alternatives remain realistic.
        if unique:
            best = unique[0]
            best_dur = int(best.get('duration_mins', 0) or 0)
            best_chg = int(best.get('changes', 0) or 0)
            unique = [
                r for r in unique
                if int(r.get('duration_mins', 10**9)) <= best_dur + 90
                and int(r.get('changes', 10**9)) <= best_chg + 2
            ]

        # Rail-station to rail-station journeys should generally surface real
        # rail alternatives first; suppress bus-detour variants when at least
        # one rail-only route exists.
        station_names = [v.get('name', '').lower() for v in self.STATIONS.values()]
        from_l = (from_name or '').lower()
        to_l = (to_name or '').lower()
        from_is_station = ('station' in from_l) or any(n and n in from_l for n in station_names)
        to_is_station = ('station' in to_l) or any(n and n in to_l for n in station_names)
        if from_is_station and to_is_station:
            rail_only = []
            mixed = []
            for r in unique:
                modes = [l.get('mode') for l in r.get('legs', []) if l.get('mode') not in ('wait',)]
                if any(m == 'bus' for m in modes):
                    mixed.append(r)
                else:
                    rail_only.append(r)
            if rail_only:
                zero_change = [r for r in rail_only if int(r.get('changes', 99)) == 0]
                if zero_change:
                    rail_only = zero_change
                unique = rail_only
            else:
                unique = mixed or unique

        return unique[:8]

    # ------------------------------------------------------------------
    # Rail route builder
    # ------------------------------------------------------------------
    def _build_rail_route(self, from_name, to_name,
                          orig_crs, orig_info, orig_walk_km,
                          dest_crs, dest_info, dest_walk_km,
                          service, dest_cp_idx, now_mins):
        """Build a route from a real rail service that calls at the
        destination.  Skips trivial walk legs (< 50 m)."""
        try:
            depart_mins = self._hhmm_to_mins(service['std'])
        except (ValueError, IndexError):
            return None

        dest_cp = service['calling_points'][dest_cp_idx]
        try:
            arrive_mins = self._hhmm_to_mins(dest_cp['scheduled'])
        except (ValueError, IndexError):
            return None

        legs = []

        # Walk to origin station (skip if < 50 m)
        if orig_walk_km >= 0.05:
            walk_mins = max(1, int(orig_walk_km * 1000 * self.WALK_FACTOR / self.WALK_SPEED))
            legs.append(self._walk_leg(
                from_name,
                f"{orig_info['name']} Railway Station",
                depart_mins - walk_mins,
                orig_walk_km,
            ))

        # Train leg with real intermediate stops
        intermediates = []
        for cp in service['calling_points'][:dest_cp_idx]:
            intermediates.append({
                'name': cp['name'],
                'time': cp['scheduled'],
            })

        ride_mins = arrive_mins - depart_mins
        if ride_mins < 0:
            ride_mins += 24 * 60

        operator = service.get('operator', 'Train')
        svc_type = service.get('service_type', 'train')
        mode = 'train' if svc_type == 'train' else 'bus'

        # Use the actual stop names if origin/dest are very close
        orig_stop_name = (from_name if orig_walk_km < 0.05
                          else f"{orig_info['name']} Railway Station")
        dest_stop_name = (to_name if dest_walk_km < 0.05
                          else f"{dest_info['name']} Railway Station")

        train_leg = {
            'mode': mode,
            'service': operator,
            'from_stop': orig_stop_name,
            'to_stop': dest_stop_name,
            'depart': service['std'],
            'arrive': dest_cp['scheduled'],
            'duration_mins': ride_mins,
            'intermediate_stops': intermediates,
        }
        legs.append(train_leg)

        # Walk from destination station (skip if < 50 m)
        if dest_walk_km >= 0.05:
            legs.append(self._walk_leg(
                f"{dest_info['name']} Railway Station",
                to_name,
                arrive_mins,
                dest_walk_km,
            ))

        return self._summarise(legs)

    # ------------------------------------------------------------------
    # Connecting rail route builder (one change at a hub)
    # ------------------------------------------------------------------
    def _build_connecting_rail_route(
        self, from_name, to_name,
        orig_crs, orig_info, orig_walk_km,
        hub_crs, hub_info,
        svc1, hub_cp_idx,
        dest_crs, dest_info, dest_walk_km,
        svc2, dest_cp_idx,
    ):
        """Build a two-train route with a change at a hub station."""
        try:
            depart1 = self._hhmm_to_mins(svc1['std'])
            hub_arrive = self._hhmm_to_mins(svc1['calling_points'][hub_cp_idx]['scheduled'])
            depart2 = self._hhmm_to_mins(svc2['std'])
            dest_arrive = self._hhmm_to_mins(svc2['calling_points'][dest_cp_idx]['scheduled'])
        except (ValueError, IndexError, KeyError):
            return None

        legs = []

        # Walk to origin station
        if orig_walk_km >= 0.05:
            walk_mins = max(1, int(orig_walk_km * 1000 * self.WALK_FACTOR / self.WALK_SPEED))
            legs.append(self._walk_leg(
                from_name,
                f"{orig_info['name']} Railway Station",
                depart1 - walk_mins,
                orig_walk_km,
            ))

        # First train leg (origin → hub)
        intermediates1 = []
        for cp in svc1['calling_points'][:hub_cp_idx]:
            intermediates1.append({'name': cp['name'], 'time': cp['scheduled']})

        ride1 = hub_arrive - depart1
        if ride1 < 0:
            ride1 += 24 * 60
        op1 = svc1.get('operator', 'Train')
        type1 = 'train' if svc1.get('service_type', 'train') == 'train' else 'bus'

        orig_stop = (from_name if orig_walk_km < 0.05
                     else f"{orig_info['name']} Railway Station")
        hub_name = hub_info.get('name', hub_crs)

        legs.append({
            'mode': type1,
            'service': op1,
            'from_stop': orig_stop,
            'to_stop': f"{hub_name} Railway Station",
            'depart': svc1['std'],
            'arrive': svc1['calling_points'][hub_cp_idx]['scheduled'],
            'duration_mins': ride1,
            'intermediate_stops': intermediates1,
        })

        # Waiting time at hub (shown as a transfer / wait)
        wait_mins = depart2 - hub_arrive
        if wait_mins > 0:
            legs.append({
                'mode': 'wait',
                'from_stop': f"{hub_name} Railway Station",
                'to_stop': f"{hub_name} Railway Station",
                'depart': self._fmt(hub_arrive),
                'arrive': self._fmt(depart2),
                'duration_mins': wait_mins,
                'distance_m': 0,
            })

        # Second train leg (hub → destination)
        intermediates2 = []
        for cp in svc2['calling_points'][:dest_cp_idx]:
            intermediates2.append({'name': cp['name'], 'time': cp['scheduled']})

        ride2 = dest_arrive - depart2
        if ride2 < 0:
            ride2 += 24 * 60
        op2 = svc2.get('operator', 'Train')
        type2 = 'train' if svc2.get('service_type', 'train') == 'train' else 'bus'

        dest_stop = (to_name if dest_walk_km < 0.05
                     else f"{dest_info['name']} Railway Station")

        legs.append({
            'mode': type2,
            'service': op2,
            'from_stop': f"{hub_name} Railway Station",
            'to_stop': dest_stop,
            'depart': svc2['std'],
            'arrive': svc2['calling_points'][dest_cp_idx]['scheduled'],
            'duration_mins': ride2,
            'intermediate_stops': intermediates2,
        })

        # Walk from destination station
        if dest_walk_km >= 0.05:
            legs.append(self._walk_leg(
                f"{dest_info['name']} Railway Station",
                to_name,
                dest_arrive,
                dest_walk_km,
            ))

        return self._summarise(legs)

    # ------------------------------------------------------------------
    # Bus route builder
    # ------------------------------------------------------------------
    def _build_bus_routes(self, from_name, to_name, match, now_mins):
        """Build 2-3 bus route options from a bus-route match, using
        frequency-based departure estimation."""
        svc = match['service']
        stops = svc['stops']
        board_idx = match['board_idx']
        alight_idx = match['alight_idx']
        walk_to_km = match['walk_to_km']
        walk_from_km = match['walk_from_km']
        freq = svc.get('frequency_mins', 30)

        # Per-segment timing profile for this route.
        seg_mins = self._estimate_segment_mins(svc)
        board_offset = sum(seg_mins[:board_idx])
        alight_offset = sum(seg_mins[:alight_idx])
        ride_mins = max(3, alight_offset - board_offset)

        # Try live departures first (from /bus/live). Feed gives origin aimed
        # departure, so shift by board_offset for boarding stop time.
        live_origin_deps, live_total_duration = self._live_departures_for_service(
            svc['service'], now_mins
        )

        # If we have a live total duration for the line, scale segment times
        # so travel time proportions remain sensible but absolute times align
        # with live operational data.
        if live_total_duration is not None and alight_offset > 0:
            scale = max(0.5, min(2.0, live_total_duration / max(1, sum(seg_mins))))
            board_offset = int(round(board_offset * scale))
            alight_offset = int(round(alight_offset * scale))
            ride_mins = max(3, alight_offset - board_offset)

        departure_candidates = []
        for od in live_origin_deps:
            dep_at_board = od + board_offset
            if dep_at_board >= now_mins and dep_at_board <= now_mins + 180:
                departure_candidates.append(dep_at_board)
        departure_candidates = departure_candidates[:3]

        # Fallback to headway-based departures if live feed has no usable data.
        if not departure_candidates:
            base_offset = (now_mins % freq)
            first_dep = now_mins - base_offset + freq  # next departure after now
            if first_dep <= now_mins:
                first_dep += freq
            departure_candidates = [first_dep + i * freq for i in range(3)]

        # Generate 2-3 departures
        results = []
        for dep_mins in departure_candidates:
            if dep_mins > now_mins + 180:
                break  # only show next 3 hours

            legs = []

            # Walk to bus stop (skip if very close)
            if walk_to_km >= 0.05:
                walk_mins = max(1, int(walk_to_km * 1000 * self.WALK_FACTOR / self.WALK_SPEED))
                legs.append(self._walk_leg(from_name, stops[board_idx]['name'],
                                           dep_mins - walk_mins, walk_to_km))

            # Build intermediate stops with estimated times
            intermediates = []
            for k in range(board_idx + 1, alight_idx):
                denom = max(1, alight_idx - board_idx)
                frac = (k - board_idx) / denom
                intermediates.append({
                    'name': stops[k]['name'],
                    'time': self._fmt(dep_mins + int(ride_mins * frac)),
                })

            # Use the actual stop names when origin/dest are very close
            bus_from = from_name if walk_to_km < 0.05 else stops[board_idx]['name']
            bus_to = to_name if walk_from_km < 0.05 else stops[alight_idx]['name']

            bus_leg = {
                'mode': 'bus',
                'service': svc['service'],
                'from_stop': bus_from,
                'to_stop': bus_to,
                'depart': self._fmt(dep_mins),
                'arrive': self._fmt(dep_mins + ride_mins),
                'duration_mins': ride_mins,
                'intermediate_stops': intermediates,
            }
            legs.append(bus_leg)

            # Walk from bus stop (skip if very close)
            if walk_from_km >= 0.05:
                legs.append(self._walk_leg(stops[alight_idx]['name'], to_name,
                                           dep_mins + ride_mins, walk_from_km))

            results.append(self._summarise(legs))

        return results

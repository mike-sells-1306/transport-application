
# Mappings from HTML appendix (expand for full coverage)
TOC_CODES = {
    "88": "Northern Trains",
    "79": "Avanti West Coast",
    "20": "TransPennine Express",
    "29": "East Midlands Railway",
    # Add all TOC codes from Appendix F
}

REASON_CODES = {
    "YI": "Delay due to infrastructure",
    "TR": "Train Reinstatement",
    "CO": "Change of Origin",
    # Add all reason codes from Appendix B
}

STANOX_CODES = {
    "77301": "Manchester Piccadilly",
    "52701": "Lancaster",
    "87701": "Leeds",
    # Add all STANOX codes from Appendix A
}

NLC_CODES = {
    "LDS": "Leeds",
    "KGX": "London King's Cross",
    "LCN": "Lancaster",
    # Add all NLC codes from Appendix A
}

PLATFORM_CODES = {
    "1": "Platform 1",
    "2": "Platform 2",
    "3": "Platform 3",
    # Add all platform codes from Appendix D
}

# Add mappings for TIPLOC, ATCO, sector codes, business codes, etc. as needed


class DataTranslator:
    def translate_train_event(self, event):
        # Translate TRUST event fields using appendix mappings
        translated = {
            "train_id": event.get("train_id"),
            "train_service_code": event.get("train_service_code"),
            "toc": TOC_CODES.get(event.get("toc_id"), event.get("toc_id")),
            "location": STANOX_CODES.get(event.get("loc_stanox"), event.get("loc_stanox")),
            "reason": REASON_CODES.get(event.get("canx_reason_code"), event.get("canx_reason_code")),
            "platform": PLATFORM_CODES.get(event.get("platform"), event.get("platform")),
            # Add more fields as needed from appendix
        }
        return translated

    def translate_location(self, code):
        return STANOX_CODES.get(code) or NLC_CODES.get(code) or code

    def translate_toc(self, code):
        return TOC_CODES.get(code, code)

    def translate_reason(self, code):
        return REASON_CODES.get(code, code)

    # Add more translation methods for TIPLOC, ATCO, sector codes, business codes, etc.

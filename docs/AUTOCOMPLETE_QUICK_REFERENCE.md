# Autocomplete Quick Reference

## API Endpoint

```bash
GET /api/stops/search?q=blackpool&limit=10
```

**Response:**
```json
{
  "stops": [
    {
      "name": "Blackpool North Railway Station, Blackpool",
      "atcoCode": "9100BKPN",
      "lat": 53.8212,
      "lon": -3.0507,
      "stopType": "rail"
    }
  ]
}
```

## JavaScript Usage

### Get Selected Stops
```javascript
const stops = getSelectedStops();
// Returns: { from: {...}, to: {...} }
```

### Set Stop Programmatically
```javascript
setStop('from', {
  name: "Preston Bus Station, Preston",
  atcoCode: "2400LAA10987",
  lat: 53.7593,
  lon: -2.6993,
  stopType: "bus"
});
```

### Validate Before Submission
```javascript
function validateSearch() {
  const stops = getSelectedStops();
  return stops.from !== null && stops.to !== null;
}
```

## CSS Classes

- `.autocomplete-wrapper` - Container
- `.autocomplete-suggestions` - Dropdown
- `.autocomplete-suggestions.visible` - Show dropdown
- `.autocomplete-suggestion-item` - Individual item
- `.autocomplete-suggestion-item.selected` - Highlighted item
- `.autocomplete-no-results` - No results message

## Keyboard Shortcuts

- `↓` / `↑` - Navigate suggestions
- `Enter` - Select highlighted item
- `Escape` - Close dropdown
- `Tab` - Next input field

## Configuration

### Debounce Delay (main.js)
```javascript
debounceTimer = setTimeout(() => {
  searchStops(query, ...);
}, 300); // Change to 500 for slower typing
```

### Result Limit (main.js)
```javascript
const response = await fetch(
  `/api/stops/search?q=${query}&limit=20` // Change limit
);
```

### Geographic Bounds (app.py)
```python
MIN_LAT, MAX_LAT = 53.3665, 54.6200
MIN_LON, MAX_LON = -3.5, -2.211
```

## Troubleshooting

**No suggestions?**
- Type at least 2 characters
- Check backend is running
- Check browser console for errors

**Wrong styling?**
- Verify `style.css` is loaded
- Check z-index conflicts
- Inspect element to see applied styles

**Slow performance?**
- Increase debounce delay
- Reduce result limit
- Check backend logs for slow queries

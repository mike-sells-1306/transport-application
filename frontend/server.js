const express = require('express');
const path = require('path');
const app = express();

app.use(express.static(path.join(__dirname, 'src')));

// Proxy /api/health to backend service in docker-compose
app.get('/api/health', async (req, res) => {
  try {
    const fetch = require('node-fetch');
    const r = await fetch('http://backend:5000/health');
    const j = await r.json();
    res.json(j);
  } catch (e) {
    res.status(502).json({ error: 'backend unreachable' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Frontend listening on ${PORT}`));

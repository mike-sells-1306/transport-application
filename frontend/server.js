const express = require('express');
const path = require('path');
const app = express();

app.use(express.json());
app.use(express.static(path.join(__dirname, 'src')));

// Proxy all /api requests to backend service in docker-compose
app.use('/api', async (req, res) => {
  try {
    const targetPath = req.originalUrl;
    const backendResponse = await fetch(`http://backend:5000${targetPath}`, {
      method: req.method,
      headers: {
        'Content-Type': req.headers['content-type'] || 'application/json',
        Authorization: req.headers.authorization || '',
      },
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : JSON.stringify(req.body || {}),
    });

    const responseText = await backendResponse.text();
    res.status(backendResponse.status);

    const contentType = backendResponse.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return res.json(responseText ? JSON.parse(responseText) : {});
    }

    return res.send(responseText);
  } catch (e) {
    res.status(502).json({ error: 'backend unreachable', detail: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Frontend listening on ${PORT}`));

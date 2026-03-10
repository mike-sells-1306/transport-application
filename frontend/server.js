const express = require('express');
const path = require('path');
const app = express();

app.use(express.json());
app.use(express.static(path.join(__dirname, 'src')));

// Proxy all /api requests to backend service in docker-compose
app.use('/api', async (req, res) => {
  try {
    const targetPath = req.originalUrl;
    const requestHeaders = {};
    if (req.headers.authorization) {
      requestHeaders.Authorization = req.headers.authorization;
    }
    if (req.headers['content-type']) {
      requestHeaders['Content-Type'] = req.headers['content-type'];
    }

    const backendResponse = await fetch(`http://backend:5000${targetPath}`, {
      method: req.method,
      headers: requestHeaders,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : JSON.stringify(req.body || {}),
    });
    res.status(backendResponse.status);

    const contentType = backendResponse.headers.get('content-type') || '';
    if (contentType) {
      res.set('Content-Type', contentType);
    }

    if (contentType.includes('application/json')) {
      const responseText = await backendResponse.text();
      return res.json(responseText ? JSON.parse(responseText) : {});
    }

    const responseBuffer = Buffer.from(await backendResponse.arrayBuffer());
    return res.send(responseBuffer);
  } catch (e) {
    res.status(502).json({ error: 'backend unreachable', detail: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Frontend listening on ${PORT}`));

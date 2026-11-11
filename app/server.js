const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

app.get('/api/health', (req, res) => {
    res.json({
        status: 'up',
        service: 'Report-API',
        dependencies: [
            { name: 'admin-dashboard', host: 'internal-dashboard', port: 5000 }
        ]
    });
});

app.post('/api/fetch-vendor-data', async (req, res) => {
    const { vendorUrl } = req.body;

    if (!vendorUrl) {
        return res.status(400).json({ error: 'vendorUrl is required' });
    }

    try {
        const response = await axios.get(vendorUrl, { timeout: 3000 });
        
        res.json({
            message: 'Vendor data fetched successfully',
            data: response.data
        });
    } catch (error) {
        res.status(500).json({ error: 'Failed to fetch vendor data', details: error.message });
    }
});

app.listen(3000, () => {
    console.log('Enterprise Report Service listening on port 3000');
});
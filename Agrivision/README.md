# Agrivision

Climate-smart **crop recommendation** for Saudi agriculture.  
Team Agrivision · ITU AI Readiness Hackathon (KSA).

Pick a location → soil + weather → ML ranking → policy-aware crop suggestions.

**Live app:** https://agrivision-bwji.onrender.com/

---

## Features

- Location on map / GPS
- Open data: SoilGrids + Open-Meteo
- Models: Random Forest, SVM, Gradient Boosting (blend)
- Arid / water-efficiency policy re-ranking
- PWA web app

---

## Run locally

```bash
chmod +x serve.sh && ./serve.sh
```

Open http://127.0.0.1:5001/

Retrain models (optional):

```bash
cd backend/python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ml.train
```

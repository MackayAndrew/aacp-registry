"""
AACP Community Registry API
FastAPI -- deploys to Railway in minutes.

Endpoints:
  GET /                 info
  GET /health           health check
  GET /rules            all 241 rules
  GET /rules?domain=HR  filter by domain
  GET /rules?task=FETCH filter by task
  GET /rules?q=payroll  tag search
  GET /rules?id=hr-...  single rule
"""

import json
from pathlib import Path
from collections import Counter
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="AACP Community Registry",
    description="241 pre-validated AACP v1.1 coordination rules across 7 domains.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_RULES = None

def load_rules():
    global _RULES
    if _RULES is None:
        rules_path = Path(__file__).parent / "rules.json"
        with open(rules_path) as f:
            data = json.load(f)
        _RULES = data if isinstance(data, list) else data.get("rules", [])
    return _RULES


@app.get("/")
def root():
    rules = load_rules()
    return {
        "name":         "AACP Community Registry",
        "version":      "1.0.0",
        "aacp_version": "1.1",
        "rules":        len(rules),
        "domains":      ["HR","FIN","SALES","LEGAL","IT","CS","MKT"],
        "endpoints": {
            "all_rules":   "/rules",
            "by_domain":   "/rules?domain=HR",
            "by_task":     "/rules?task=FETCH",
            "search":      "/rules?q=payroll+salary",
            "single_rule": "/rules?id=hr-fetch-active-employee-salaries",
            "health":      "/health",
        },
    }


@app.get("/health")
def health():
    rules = load_rules()
    return {
        "status":       "ok",
        "rules_loaded": len(rules),
        "version":      "1.0.0",
        "aacp_version": "1.1",
    }


VALID_DOMAINS = {"HR","FIN","SALES","LEGAL","IT","CS","MKT"}
VALID_TASKS   = {"FETCH","PROC","FLAG","RESOLVE","LOG","SEND",
                 "BUILD","MERGE","CALC","REPORT","ACK","SYNC"}


@app.get("/rules")
def get_rules(
    domain: str = Query(None),
    task:   str = Query(None),
    id:     str = Query(None),
    q:      str = Query(None),
    limit:  int = Query(50),
    offset: int = Query(0),
):
    all_rules = load_rules()
    results   = all_rules

    if id:
        match = next((r for r in results if r["id"] == id.lower()), None)
        if match:
            return JSONResponse(content=match)
        return JSONResponse(status_code=404,
                            content={"error": f"Rule not found: {id}"})

    if domain:
        domain = domain.upper()
        if domain not in VALID_DOMAINS:
            return JSONResponse(status_code=400,
                content={"error": f"Unknown domain: {domain}",
                         "valid": sorted(VALID_DOMAINS)})
        results = [r for r in results if r["dom"] == domain]

    if task:
        task = task.upper()
        if task not in VALID_TASKS:
            return JSONResponse(status_code=400,
                content={"error": f"Unknown task: {task}",
                         "valid": sorted(VALID_TASKS)})
        results = [r for r in results if r["task"] == task]

    if q:
        words  = set(q.replace("+", " ").lower().split())
        scored = []
        for rule in results:
            pool  = (set(t.lower() for t in rule.get("tags", []))
                     | set(rule.get("name","").lower().split())
                     | set(rule.get("description","").lower().split()))
            score = len(words & pool)
            if score > 0:
                scored.append((score, rule))
        scored.sort(key=lambda x: -x[0])
        results = [r for _, r in scored]

    total  = len(results)
    paged  = results[offset:offset + limit]

    response = {
        "total": total, "count": len(paged),
        "offset": offset, "limit": limit,
        "rules": paged,
    }
    if domain: response["domain"] = domain
    if task:   response["task"]   = task
    if q:      response["query"]  = q

    if not domain and not task and not q:
        response["by_domain"] = dict(Counter(r["dom"]  for r in all_rules))
        response["by_task"]   = dict(Counter(r["task"] for r in all_rules))

    return JSONResponse(content=response)

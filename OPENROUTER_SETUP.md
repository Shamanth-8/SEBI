# 🔧 OpenRouter Configuration Guide for RegGraph

## ✅ What's Been Set Up

Your `.env` file is configured to use **OpenRouter API** by default with your provided API key:

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE
OPENROUTER_MODEL=anthropic/claude-3-sonnet
```

## 📋 Quick Start

### 1. Install Dependencies

```bash
cd /run/media/shamath/C4CAC629CAC61796/code/sebi/regraph

# Install or upgrade packages
pip install -r requirements.txt

# Key packages for OpenRouter:
# - openai==1.3.8 (for OpenRouter API)
# - anthropic==0.7.1 (for direct Claude API fallback)
```

### 2. Verify Configuration

```bash
# Check .env file
cat .env | grep -E "LLM_PROVIDER|OPENROUTER|ANTHROPIC"

# Should show:
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=sk-or-v1-...
# OPENROUTER_MODEL=anthropic/claude-3-sonnet
```

### 3. Test the Setup

```bash
cd backend

# Test OpenRouter connection
python -c "
from app.anthropic_adapter import create_anthropic_compatible_client
from app.config import get_settings

settings = get_settings()
print(f'Provider: {settings.LLM_PROVIDER}')
print(f'Model: {settings.LLM_MODEL}')

# Create client
client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
print('✓ OpenRouter client initialized successfully!')

# Test message
response = client.messages.create(
    messages=[{'role': 'user', 'content': 'Say hi'}],
    max_tokens=100
)
print(f'✓ Test response: {response.content[0].text[:50]}...')
"
```

### 4. Run RegGraph

```bash
# Terminal 1: Start the API
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Start the Dashboard
cd frontend
streamlit run dashboard.py

# Open browser
open http://localhost:8501
```

## 🔄 Switching Between Providers

### Use OpenRouter (Default - Current Setup)

```bash
# In .env:
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3-sonnet
```

**Benefits:**
- ✅ Cost-effective (pay per token)
- ✅ Access to multiple models
- ✅ Route to fastest available provider
- ✅ No vendor lock-in

### Switch to Direct Claude API

```bash
# In .env:
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# Leave OPENROUTER_API_KEY empty or commented
```

**Benefits:**
- ✅ Official Anthropic provider
- ✅ Potentially lower latency
- ✅ Direct support

## 🎯 OpenRouter Model Options

Update `OPENROUTER_MODEL` in `.env` to use different models:

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `anthropic/claude-3-haiku` | ⚡ Fast | 💰 Cheap | Simple tasks, testing |
| `anthropic/claude-3-sonnet` | ✅ Balanced | ✅ Good | General use (CURRENT) |
| `anthropic/claude-3-opus` | 🐢 Slow | 💸 Expensive | Complex reasoning |
| `anthropic/claude-3.5-sonnet` | ✅ Balanced | ✅ Good | Newest, recommended |
| `meta-llama/llama-3-70b-instruct` | ✅ Good | 💰 Cheap | Open source alternative |

### Example: Switch to Claude 3.5 Sonnet (Newest)

```bash
# In .env:
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

### Example: Switch to Haiku (Cheapest/Fastest)

```bash
# In .env:
OPENROUTER_MODEL=anthropic/claude-3-haiku
```

## 📊 API Compatibility Matrix

| Feature | Anthropic Direct | OpenRouter |
|---------|------------------|-----------|
| Claude 3 models | ✅ Yes | ✅ Yes |
| Claude 3.5 models | ✅ Yes | ✅ Yes |
| Function calling | ✅ Yes | ✅ Yes |
| Vision (images) | ✅ Yes | ✅ Yes (on some) |
| Cost tracking | ✅ Detailed | ✅ Detailed |
| Rate limits | ✅ Per account | ✅ Per account |
| Other LLMs | ❌ No | ✅ Yes (70+ models) |

## 🔐 Security Best Practices

### 1. Keep API Key Safe

```bash
# ✅ DO: Use .env file (already in .gitignore)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-***

# ❌ DON'T: Commit .env to git
# ❌ DON'T: Log API keys to console
# ❌ DON'T: Share key in code files
```

### 2. .gitignore Already Configured

```bash
# Check .gitignore includes .env
cat .gitignore | grep ".env"
# Should output: .env
```

### 3. Rotate Key If Exposed

```bash
# If key is leaked:
# 1. Go to https://openrouter.ai/keys
# 2. Delete the exposed key
# 3. Generate new key
# 4. Update .env with new key
```

## 🐛 Troubleshooting

### Problem: "OPENROUTER_API_KEY not set"

```bash
# Solution: Check .env file
cat .env | grep OPENROUTER_API_KEY

# Should show your key (last 10 chars visible)
# If empty, add it:
echo "OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY" >> .env
```

### Problem: "401 Unauthorized"

```bash
# Solution: Verify API key is correct
curl -X GET https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer sk-or-v1-YOUR_KEY"

# Should return list of available models
```

### Problem: "Rate limit exceeded"

```bash
# Solution: Increase timeout or reduce concurrent requests
# In .env:
LLM_TIMEOUT=180  # Increased from default
```

### Problem: Model not found

```bash
# Solution: Check available models
curl -s https://openrouter.ai/api/v1/models | jq '.'

# Update OPENROUTER_MODEL to valid model ID
```

### Problem: Agents still using Anthropic SDK directly

```bash
# Solution: Agents are already updated to use adapter
# Check extraction_agent.py imports:
grep "anthropic_adapter" backend/app/agents/*.py

# Should show imports in all agent files
```

## 📈 Monitoring Usage

### View OpenRouter Dashboard

1. Go to https://openrouter.ai
2. Sign in with your account
3. Click "Keys" or "Dashboard"
4. See:
   - Total tokens used
   - Cost breakdown by model
   - Usage graphs
   - Request history

### Monitor via RegGraph API

```bash
# Get usage statistics (if implemented)
curl http://localhost:8000/api/v1/stats/llm-usage
```

### Log API Calls

```python
# In config.py, increase logging:
LOG_LEVEL=DEBUG  # Shows all API calls
```

## 💡 Pro Tips

### 1. Use Different Models for Different Tasks

```python
# Fast extraction - use Haiku
OPENROUTER_MODEL=anthropic/claude-3-haiku

# Later for complex diffing - switch to Opus
OPENROUTER_MODEL=anthropic/claude-3-opus
```

### 2. Batch Process to Save Cost

```python
# Process multiple circulars together
# instead of one at a time
```

### 3. Cache Responses

```python
# RegGraph automatically caches
# obligation extractions to reduce
# redundant API calls
```

### 4. Compare Providers

```bash
# Test cost difference
# Haiku: $0.00015 per 1K input
# Sonnet: $0.003 per 1K input
# Opus: $0.015 per 1K input

# For 1 million input tokens:
# Haiku: $0.15
# Sonnet: $3.00
# Opus: $15.00
```

## 🚀 Production Deployment

### Environment Variables for Production

```bash
# .env.production
ENVIRONMENT=production
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}  # Set via secrets manager
LOG_LEVEL=INFO
DEBUG=false
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: regraph-secrets
type: Opaque
stringData:
  OPENROUTER_API_KEY: sk-or-v1-...
  ANTHROPIC_API_KEY: sk-ant-...
```

### Docker Setup

```dockerfile
FROM python:3.10

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

Build with:
```bash
docker build -t regraph .
docker run -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY regraph
```

## 📚 Resources

- **OpenRouter Docs**: https://openrouter.ai/docs
- **Claude API Docs**: https://docs.anthropic.com
- **Model Prices**: https://openrouter.ai/docs/models
- **Rate Limits**: https://openrouter.ai/docs/limits

## ✅ Verification Checklist

- [ ] `.env` file created in project root
- [ ] `LLM_PROVIDER=openrouter` is set
- [ ] `OPENROUTER_API_KEY` is configured correctly
- [ ] `requirements.txt` includes `openai==1.3.8`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Adapter module: `backend/app/anthropic_adapter.py` exists
- [ ] Agents updated to use adapter
- [ ] Test passed: `python -c "from app.anthropic_adapter import create_anthropic_compatible_client; print('✓')`
- [ ] API starts: `python -m uvicorn app.main:app --reload`
- [ ] Dashboard loads: `streamlit run frontend/dashboard.py`

---

**You're all set! RegGraph is now configured to work with OpenRouter API! 🚀**

To start using it:
```bash
cd backend && python -m uvicorn app.main:app --reload &
cd ../frontend && streamlit run dashboard.py
```

Then open http://localhost:8501 and start processing compliance requirements!

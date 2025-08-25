# 🔄 **Switching from Ollama to LLM Server (LM Studio)**

## **Overview**
This guide explains how to switch from Ollama to LLM Server (LM Studio) for the KnowledgeForge ontology extraction service.

## **What Changed**

### **1. Configuration Updates**
- **Config File**: `config.yaml` now uses `lmstudio` instead of `ollama`
- **Port**: Changed from `11434` (Ollama) to `1234` (LLM Server)
- **API Endpoints**: Updated to use LLM Server's OpenAI-compatible API

### **2. Code Changes**
- **LLM Manager**: Updated to use LM Studio's `/v1/chat/completions` endpoint
- **Request Format**: Changed from Ollama's format to OpenAI-compatible format
- **Model Names**: Updated to use LLM Server compatible model names

## **Setup Instructions**

### **Step 1: Install LLM Server (LM Studio)**
1. Download LM Studio from [https://lmstudio.ai/](https://lmstudio.ai/)
2. Install and launch the application

### **Step 2: Download Models**
1. In LLM Server (LM Studio), go to the "Models" tab
2. Search for and download one of these models:
   - `llama2` (recommended)
   - `mistral`
   - `phi3`
   - `codellama`

### **Step 3: Start Local Server**
1. In LLM Server (LM Studio), go to the "Local Server" tab
2. Select your downloaded model
3. Click "Start Server"
4. The server will start on `http://localhost:1234`

### **Step 4: Verify Connection**
```bash
curl http://localhost:1234/v1/models
```
You should see a JSON response with available models.

## **Configuration**

### **Default Config (`config.yaml`)**
```yaml
lmstudio:
  base_url: "http://localhost:1234"
  model_name: "llama2"
  temperature: 0.7
  max_tokens: 100
  timeout: 30
  retry_attempts: 3
  use_embeddings: true
  embedding_model: "all-MiniLM-L6-v2"
  # LM Studio specific settings
  context_length: 4096
  stop_sequences: ["</s>", "<|endoftext|>"]
  top_p: 0.9
  top_k: 40
```

### **Environment Variables**
```bash
export ONTOLOGY_LMSTUDIO__BASE_URL="http://localhost:1234"
export ONTOLOGY_LMSTUDIO__MODEL_NAME="llama2"
```

## **Starting the Service**

### **Option 1: Local Development**
```bash
cd sources/Api
python3 main.py
```

### **Option 2: Docker Compose**
```bash
cd sources/Api
docker-compose up -d neo4j
# Note: LM Studio runs locally, not in Docker
```

## **Testing the Integration**

### **Test API Health**
```bash
curl http://localhost:8000/health
```

### **Test LLM Connection**
```bash
curl http://localhost:8000/metrics
```

### **Test Extraction**
```bash
curl -X POST http://localhost:8000/extract \
  -H "X-API-Key: your-api-key" \
  -F "file=@your-data.csv"
```

## **Troubleshooting**

### **Common Issues**

1. **Connection Refused**
   - Ensure LM Studio local server is running
   - Check if port 1234 is available
   - Verify firewall settings

2. **Model Not Found**
   - Check if model is downloaded in LM Studio
   - Verify model name in configuration
   - Restart LM Studio local server

3. **API Errors**
   - Check LM Studio logs
   - Verify API endpoint format
   - Check model compatibility

### **Logs**
- **LM Studio**: Check the Local Server tab for errors
- **KnowledgeForge API**: Check console output or log files

## **Performance Tips**

1. **Model Selection**: Use smaller models (7B) for faster inference
2. **Context Length**: Adjust based on your use case
3. **Batch Processing**: Use appropriate batch sizes for your hardware
4. **Caching**: Enable response caching for repeated queries

## **Migration Checklist**

- [ ] Install LM Studio
- [ ] Download compatible models
- [ ] Start local server
- [ ] Update configuration
- [ ] Test connection
- [ ] Verify extraction works
- [ ] Update deployment scripts
- [ ] Test in production environment

## **Support**

If you encounter issues:
1. Check LM Studio documentation
2. Verify model compatibility
3. Check KnowledgeForge logs
4. Test with simple prompts first

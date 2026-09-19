// BAML Configuration for AI-Native Multi-Agent ERP
// Generators and Client definitions

generator python {
  output_type "python/pydantic"
  output_dir "../src/erp/baml_client"
  version "0.65.0"
}

client<llm> GeminiPro {
  provider "google-ai"
  options {
    model "gemini-1.5-pro"
    api_key env.GEMINI_API_KEY
  }
}

client<llm> GeminiFlash {
  provider "google-ai"
  options {
    model "gemini-1.5-flash"
    api_key env.GEMINI_API_KEY
  }
}

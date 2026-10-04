import os
import sys

sys.path.insert(0, "app")
import agent_brain as a
import litellm

model = (os.getenv("GROQ_MODEL") or a.DEFAULT_GROQ_MODEL).strip()
print("Model:", model)

try:
    r = litellm.completion(
        model="groq/" + model.replace("groq/", ""),
        api_key=os.getenv("GROQ_API_KEY"),
        messages=[{"role": "user", "content": "Say hi"}],
    )
    print("TEST A OK:", r.choices[0].message.content)
except Exception as e:
    print("TEST A FAILED:", type(e).__name__, str(e)[:600])

try:
    llm = a._build_llm()
    monitor = a._make_agents(llm)[0]
    print("TEST B OK:", a._run_task(monitor, "Reply with: hi", "text")[:200])
except Exception as e:
    print("TEST B FAILED:", type(e).__name__, str(e)[:600])

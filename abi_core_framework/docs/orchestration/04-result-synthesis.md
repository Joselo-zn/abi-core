# Result Synthesis

After a workflow completes, the Orchestrator combines all agent responses into one coherent answer for the user.

## How it works

1. Workflow executes all tasks → each agent returns a result
2. Orchestrator collects all results
3. If there are artifacts (files), generates download URLs
4. Calls the LLM with a synthesis prompt containing the plan + all results
5. Returns the synthesized response to the user

## The synthesis step (from the Orchestrator)

```python
# After workflow completes
if workflow.state == Status.COMPLETED:
    # Collect artifacts from agent responses
    artifacts = []
    for r in results:
        resp = A2AResponse.parse(r)
        if resp and resp.data:
            for art in resp.data.get("uploaded_artifacts", []):
                artifacts.append(art)

    # Generate download URLs for artifacts
    await generate_download_urls(artifacts)

    # Build synthesis prompt
    synthesis_query = (
        f"Synthesize the following workflow results:\n"
        f"Plan: {json.dumps(plan, indent=2)}\n"
        f"Results count: {len(results)}\n"
    )
    if artifacts:
        synthesis_query += "Generated artifacts:\n"
        for art in artifacts:
            synthesis_query += f"  - {art['filename']}: {art['download_url']}\n"

    # Call LLM to synthesize
    final_response = await invoke(config.LLM_CONFIG, synthesis_query)

    # Append artifact links if the LLM didn't include them
    if artifacts and "download" not in final_response.lower():
        final_response += format_artifact_links(artifacts)

    yield AgentResponse.success(final_response)
```

## What the user sees

```
event: status → "Analyzing request..."
event: status → "Processing..." (heartbeats)
event: status → "Synthesizing results..."
event: result → "Based on the analysis, Q4 revenue grew 15%...
                 📎 Download report: https://minio.../report.pdf"
```

## Artifacts

Agents can upload files (PDFs, CSVs, images) to the Artifact Store (MinIO). The Orchestrator:

1. Extracts artifact metadata from agent responses
2. Generates pre-signed download URLs
3. Includes them in the synthesis

```python
from abi_core.common.artifact_store import generate_download_urls, format_artifact_links

await generate_download_urls(artifacts)
links = format_artifact_links(artifacts)
# "📎 report.pdf: https://minio.../presigned-url"
```

## Error handling

If a workflow fails partway through:

```python
if dag_result.get("failed_node"):
    error = dag_result.get("error", "Pipeline failed")
    self._record_error(context_id, "dag_failed", error)
    yield AgentResponse.error(error)
    return
```

The Orchestrator records the error in session context so the next request is aware of what failed.

## Next step

👉 [RAG & Knowledge](../rag/01-what-is-rag.md)

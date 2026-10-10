---
updatedAt: 2026-06-26T05:14:45.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Connect to Leonardo.Ai with the MCP Server

The Leonardo.Ai Connector allows your AI assistant to seamlessly interact with Leonardo.ai’s image generation capabilities. The connector uses the Model Context Protocol (MCP) to enable your AI assistant to create new images.

# Before you start

To use the Leonardo.Ai Connector, you’ll need:

* An AI assistant that can use MCP servers, such as:
  * Cursor
  * VS Code (with a compatible plugin or extension, such as GitHub Copilot)
* A Leonardo.Ai account
* Any Leonardo.Ai [API plan](https://leonardo.ai/pricing/)

# Connect your AI assistant

## Create an API Key

The Leonardo.Ai Connector currently requires an API key to be created. Follow the instructions <Anchor target="_blank" href="https://docs.leonardo.ai/docs/getting-started#step-1-subscribe--get-your-api-key">here</Anchor> to create your API Key before continuing.

## Configure your AI assistant

Each AI assistant requires specific configuration to communicate with the Leonardo.Ai Connector. Follow the instructions below for your assistant.

## Cursor

<Callout icon="ℹ️" theme="info">
  ###

  MCP tools are currently only available in Agent mode.
</Callout>

<br />

You can manually create the configuration with the following steps:

1. If you haven’t already configured an MCP server in your project directory, create the configuration directory and file:
   ```
   mkdir -p .cursor
   touch .cursor/mcp.json
   ```
2. Add the following configuration for the Leonardo.Ai MCP server to .`cursor/mcp.json`:
   ```
   {
     "mcpServers": {
       "leonardo-ai": {
         "url": "https://mcp.leonardo.ai/v1/mcp",
         "headers": {
           "API-Key": "replace this string with your api key"
         }
       }
     }
   }
   ```

For more information, see the <Anchor target="_blank" href="https://cursor.com/docs/mcp#installing-mcp-servers">Cursor MCP documentation</Anchor>.

<br />

## Check the connection

### To confirm the Leonardo.Ai Connector is working:

Look for visual indicators in your AI assistant app.
For example, in Cursor you can go to Cursor Settings → MCP and see the Leonardo.Ai MCP server listed.

<br />

# Tools available to Leonardo.ai Connector

## Image Generation & Management

* **generate-image** - Create images with prompts, models, dimensions, guidance scale, etc. Models currently supported:
  * **Lucid Origin (HD Generalist)**: Best for general image generation with diverse styles
  * **Lucid Realism (Hyperrealistic)**: Best for ultra-realistic and photorealistic images
  * **Ideogram 3.0 (Accurate Text Rendering)**: Best for images with text and design work

<Callout icon="📘" theme="info">
  ###

  New tools and models will be added to our MCP Server over time. If you need a tool or model that isn't supported by it yet, please use the [API](https://docs.leonardo.ai/docs/generate-your-first-images#/) functionality.
</Callout>

<br />
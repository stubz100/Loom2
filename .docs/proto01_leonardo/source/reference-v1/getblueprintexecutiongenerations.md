---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get Blueprint Execution Generations by Execution ID

Retrieves paginated generations for a specific Blueprint Execution, including their statuses and any prompt moderation failure details.

# OpenAPI definition

```json
{
  "openapi": "3.0.0",
  "info": {
    "description": "Leonardo.Ai API OpenAPI specification (v1.0).",
    "title": "Rest Endpoints",
    "version": "v1.0.0"
  },
  "servers": [
    {
      "url": "https://cloud.leonardo.ai/api/rest/v1",
      "description": "Leonardo.Ai API server"
    }
  ],
  "tags": [
    {
      "name": "Blueprints"
    }
  ],
  "paths": {
    "/blueprint-executions/{id}/generations": {
      "get": {
        "tags": [
          "Blueprints"
        ],
        "summary": "Get Blueprint Execution Generations by Execution ID",
        "description": "Retrieves paginated generations for a specific Blueprint Execution, including their statuses and any prompt moderation failure details.",
        "operationId": "getBlueprintExecutionGenerations",
        "parameters": [
          {
            "required": true,
            "in": "path",
            "name": "id",
            "description": "The akUUID of the Blueprint Execution to retrieve generations for",
            "schema": {
              "$ref": "#/components/schemas/uuid"
            }
          },
          {
            "required": false,
            "in": "query",
            "name": "first",
            "description": "Number of generations to return from the beginning of the list (forward pagination)",
            "schema": {
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            }
          },
          {
            "required": false,
            "in": "query",
            "name": "after",
            "description": "Cursor for forward pagination - returns generations after this cursor",
            "schema": {
              "$ref": "#/components/schemas/Cursor"
            }
          },
          {
            "required": false,
            "in": "query",
            "name": "last",
            "description": "Number of generations to return from the end of the list (backward pagination)",
            "schema": {
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            }
          },
          {
            "required": false,
            "in": "query",
            "name": "before",
            "description": "Cursor for backward pagination - returns generations before this cursor",
            "schema": {
              "$ref": "#/components/schemas/Cursor"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Blueprint Execution Generations",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "blueprintExecutionGenerations": {
                      "$ref": "#/components/schemas/BlueprintExecutionGenerationsConnection"
                    }
                  }
                },
                "examples": {
                  "success": {
                    "summary": "Successful response with generations",
                    "value": {
                      "blueprintExecutionGenerations": {
                        "pageInfo": {
                          "hasNextPage": true,
                          "hasPreviousPage": false,
                          "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                          "endCursor": "YXJyYXljb25uZWN0aW9uOjE5"
                        },
                        "edges": [
                          {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                            "node": {
                              "akUUID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                              "status": "COMPLETED",
                              "generationId": "1f0bba44-923a-69b0-b519-62a6710d46a9"
                            }
                          },
                          {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjE=",
                            "node": {
                              "akUUID": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                              "status": "FAILED",
                              "generationId": "1f0b933e-b512-6640-8305-4835ab8cebfd",
                              "failedReason": {
                                "type": "PROMPT_MODERATION_BLOCKED",
                                "message": "Content policy violation: Content involving minors combined with NSFW content is strictly prohibited. Please modify your prompt and try again.",
                                "affectedOutputCount": 1
                              }
                            }
                          }
                        ]
                      }
                    }
                  },
                  "promptModerationFailure": {
                    "summary": "Generation failed due to prompt moderation",
                    "value": {
                      "blueprintExecutionGenerations": {
                        "pageInfo": {
                          "hasNextPage": false,
                          "hasPreviousPage": false,
                          "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                          "endCursor": "YXJyYXljb25uZWN0aW9uOjA="
                        },
                        "edges": [
                          {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                            "node": {
                              "akUUID": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                              "status": "FAILED",
                              "generationId": "1f0b933e-b512-6640-8305-4835ab8cebfd",
                              "failedReason": {
                                "type": "PROMPT_MODERATION_BLOCKED",
                                "message": "Content policy violation: Content involving minors combined with NSFW content is strictly prohibited. Please modify your prompt and try again.",
                                "affectedOutputCount": 4
                              }
                            }
                          }
                        ]
                      }
                    }
                  },
                  "notAccessible": {
                    "summary": "Blueprint Execution not accessible or not found",
                    "value": {
                      "blueprintExecutionGenerations": {
                        "pageInfo": {
                          "hasNextPage": false,
                          "hasPreviousPage": false,
                          "startCursor": null,
                          "endCursor": null
                        },
                        "edges": []
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "Cursor": {
        "type": "string",
        "title": "Cursor",
        "description": "An opaque cursor used for pagination"
      },
      "BlueprintExecutionGenerationsConnection": {
        "type": "object",
        "nullable": false,
        "title": "BlueprintExecutionGenerationsConnection",
        "description": "A paginated connection of Blueprint Execution Generations",
        "properties": {
          "pageInfo": {
            "$ref": "#/components/schemas/pageInfo"
          },
          "edges": {
            "type": "array",
            "description": "List of generation edges",
            "items": {
              "$ref": "#/components/schemas/BlueprintExecutionGenerationEdge"
            }
          }
        },
        "required": [
          "pageInfo",
          "edges"
        ]
      },
      "BlueprintExecutionGenerationEdge": {
        "type": "object",
        "nullable": false,
        "title": "BlueprintExecutionGenerationEdge",
        "description": "An edge containing a Blueprint Execution Generation node",
        "properties": {
          "cursor": {
            "$ref": "#/components/schemas/Cursor",
            "description": "Cursor for this edge, used for pagination"
          },
          "node": {
            "$ref": "#/components/schemas/BlueprintExecutionGeneration"
          }
        },
        "required": [
          "cursor",
          "node"
        ]
      },
      "BlueprintExecutionGeneration": {
        "type": "object",
        "nullable": false,
        "title": "BlueprintExecutionGeneration",
        "description": "Represents a single generation within a Blueprint Execution",
        "properties": {
          "akUUID": {
            "allOf": [
              {
                "$ref": "#/components/schemas/uuid"
              },
              {
                "nullable": false,
                "description": "Unique identifier for the Blueprint Execution Generation"
              }
            ]
          },
          "status": {
            "$ref": "#/components/schemas/BlueprintExecutionGenerationStatus",
            "description": "Status of the generation"
          },
          "generationId": {
            "type": "string",
            "nullable": false,
            "description": "The generation ID associated with this execution generation",
            "example": "1f0bba44-923a-69b0-b519-62a6710d46a9"
          },
          "failedReason": {
            "$ref": "#/components/schemas/PromptModerationFailureReason",
            "description": "Details about why the generation failed, specifically for prompt moderation failures"
          }
        },
        "required": [
          "akUUID",
          "status",
          "generationId"
        ]
      },
      "BlueprintExecutionGenerationStatus": {
        "type": "string",
        "nullable": false,
        "title": "BlueprintExecutionGenerationStatus",
        "enum": [
          "PENDING",
          "COMPLETED",
          "FAILED"
        ],
        "description": "The status of a Blueprint Execution Generation"
      },
      "PromptModerationFailureReason": {
        "type": "object",
        "nullable": true,
        "title": "PromptModerationFailureReason",
        "description": "Details about a generation failure due to prompt moderation",
        "properties": {
          "type": {
            "type": "string",
            "nullable": false,
            "enum": [
              "PROMPT_MODERATION_BLOCKED"
            ],
            "description": "The type of failure - PROMPT_MODERATION_BLOCKED indicates the prompt was blocked by content moderation",
            "example": "PROMPT_MODERATION_BLOCKED"
          },
          "message": {
            "type": "string",
            "nullable": false,
            "description": "Human-readable message describing the failure",
            "example": "Generation blocked due to prompt moderation"
          },
          "affectedOutputCount": {
            "type": "integer",
            "nullable": false,
            "description": "Number of outputs affected by this failure",
            "example": 1
          }
        },
        "required": [
          "type",
          "message",
          "affectedOutputCount"
        ]
      },
      "uuid": {
        "nullable": true,
        "pattern": "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}",
        "title": "uuid",
        "type": "string"
      },
      "pageInfo": {
        "type": "object",
        "title": "PageInfo",
        "description": "Pagination information following the Relay cursor pagination spec",
        "properties": {
          "hasNextPage": {
            "type": "boolean",
            "description": "Whether there is a next page"
          },
          "hasPreviousPage": {
            "type": "boolean",
            "description": "Whether there is a previous page"
          },
          "startCursor": {
            "allOf": [
              {
                "$ref": "#/components/schemas/Cursor"
              }
            ],
            "description": "Cursor for the first item in the result set"
          },
          "endCursor": {
            "allOf": [
              {
                "$ref": "#/components/schemas/Cursor"
              }
            ],
            "description": "Cursor for the last item in the result set"
          }
        }
      }
    },
    "securitySchemes": {
      "bearerAuth": {
        "type": "http",
        "bearerFormat": "auth-scheme",
        "description": "Bearer HTTP authentication. Allowed headers `Authorization: Bearer <api_key>`",
        "scheme": "bearer"
      }
    }
  },
  "security": [
    {
      "bearerAuth": []
    }
  ]
}
```
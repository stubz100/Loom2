---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Execute a Blueprint

Execute a Blueprint Version with custom node inputs. This endpoint triggers the execution of the specified Blueprint Version and returns a Blueprint Execution ID to track the job.

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
    "/blueprint-executions": {
      "post": {
        "tags": [
          "Blueprints"
        ],
        "summary": "Execute a Blueprint",
        "description": "Execute a Blueprint Version with custom node inputs. This endpoint triggers the execution of the specified Blueprint Version and returns a Blueprint Execution ID to track the job.",
        "operationId": "executeBlueprint",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": [
                  "blueprintVersionId",
                  "input"
                ],
                "properties": {
                  "blueprintVersionId": {
                    "type": "string",
                    "format": "uuid",
                    "description": "The unique identifier of the Blueprint Version to execute",
                    "example": "550e8400-e29b-41d4-a716-446655440000"
                  },
                  "input": {
                    "type": "object",
                    "required": [
                      "nodeInputs",
                      "public"
                    ],
                    "properties": {
                      "nodeInputs": {
                        "type": "array",
                        "description": "Array of node input objects to customize the Blueprint",
                        "items": {
                          "$ref": "#/components/schemas/NodeInput"
                        }
                      },
                      "public": {
                        "type": "boolean",
                        "description": "Whether the resulting generations should be public",
                        "example": false
                      },
                      "collectionIds": {
                        "type": "array",
                        "items": {
                          "$ref": "#/components/schemas/bigint"
                        },
                        "description": "Optional list of collection IDs to add the generations to",
                        "example": []
                      }
                    }
                  }
                }
              },
              "example": {
                "blueprintVersionId": "550e8400-e29b-41d4-a716-446655440000",
                "input": {
                  "nodeInputs": [
                    {
                      "nodeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                      "settingName": "text",
                      "value": "A futuristic cityscape at sunset"
                    },
                    {
                      "nodeId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                      "settingName": "textVariables",
                      "value": [
                        {
                          "name": "characterName",
                          "value": "Luna"
                        },
                        {
                          "name": "outfit",
                          "value": "cyberpunk armor"
                        }
                      ]
                    },
                    {
                      "nodeId": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                      "settingName": "imageUrl",
                      "value": "https://cdn.leonardo.ai/users/example/image.png"
                    }
                  ],
                  "public": false,
                  "collectionIds": []
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "oneOf": [
                    {
                      "type": "object",
                      "title": "Success Response",
                      "required": [
                        "executeBlueprint"
                      ],
                      "properties": {
                        "executeBlueprint": {
                          "type": "object",
                          "required": [
                            "akUUID"
                          ],
                          "properties": {
                            "akUUID": {
                              "type": "string",
                              "format": "uuid",
                              "description": "The unique identifier of the Blueprint Execution",
                              "example": "550e8400-e29b-41d4-a716-446655440000"
                            }
                          }
                        }
                      }
                    },
                    {
                      "type": "array",
                      "title": "Error Response",
                      "description": "Error response when validation fails",
                      "items": {
                        "$ref": "#/components/schemas/ApiError"
                      }
                    }
                  ]
                },
                "examples": {
                  "success": {
                    "summary": "Successful response",
                    "value": {
                      "executeBlueprint": {
                        "akUUID": "550e8400-e29b-41d4-a716-446655440000"
                      }
                    }
                  },
                  "error": {
                    "summary": "Error response",
                    "value": [
                      {
                        "message": "An error occurred.",
                        "path": [
                          "executeBlueprint"
                        ],
                        "locations": [
                          {
                            "column": 70,
                            "line": 1
                          }
                        ],
                        "extensions": {
                          "code": "BadRequestException",
                          "details": {
                            "message": "Bad request. Please check your input.",
                            "statusCode": 400
                          }
                        }
                      }
                    ]
                  }
                }
              }
            },
            "description": "Responses for POST /blueprint-executions"
          },
          "400": {
            "description": "Bad Request - Invalid input type or missing required GraphQL field",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message describing the invalid input type or missing field",
                      "example": "Invalid input type: expected 'string' for field 'blueprintVersionId'"
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
      "NodeInput": {
        "type": "object",
        "title": "NodeInput",
        "description": "A node input object for customizing a Blueprint Execution",
        "required": [
          "nodeId",
          "settingName",
          "value"
        ],
        "properties": {
          "nodeId": {
            "type": "string",
            "format": "uuid",
            "description": "The ID of the node in the Blueprint",
            "example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
          },
          "settingName": {
            "type": "string",
            "enum": [
              "text",
              "imageUrl",
              "textVariables"
            ],
            "description": "The type of setting to replace:\n- `text`: Direct text replacement (value is a string)\n- `imageUrl`: Image URL input (value is a URL string)\n- `textVariables`: Text with placeholder variables (value is an array of TextVariable)",
            "example": "text"
          },
          "value": {
            "oneOf": [
              {
                "type": "string",
                "description": "String value. Use for settingName='text' (direct text) or settingName='imageUrl' (image URL)"
              },
              {
                "type": "array",
                "items": {
                  "$ref": "#/components/schemas/TextVariable"
                },
                "description": "Array of TextVariable objects. Use only for settingName='textVariables' to replace {{placeholders}} in the Blueprint"
              }
            ],
            "description": "The replacement value. Type depends on settingName:\n- `text`: string (the full text)\n- `imageUrl`: string (the image URL)\n- `textVariables`: array of TextVariable objects",
            "example": "A futuristic cityscape at sunset"
          }
        }
      },
      "TextVariable": {
        "type": "object",
        "title": "TextVariable",
        "description": "A text variable for replacing placeholders in Blueprint templates",
        "required": [
          "name",
          "value"
        ],
        "properties": {
          "name": {
            "type": "string",
            "description": "The name of the placeholder variable (without curly braces)",
            "example": "characterName"
          },
          "value": {
            "type": "string",
            "description": "The value to replace the placeholder with",
            "example": "Luna"
          }
        }
      },
      "ApiError": {
        "type": "object",
        "title": "ApiError",
        "description": "API error response structure",
        "required": [
          "message"
        ],
        "properties": {
          "message": {
            "type": "string",
            "description": "Error message"
          },
          "path": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Path to the field that caused the error"
          },
          "locations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "column": {
                  "type": "integer"
                },
                "line": {
                  "type": "integer"
                }
              }
            },
            "description": "Location information for the error"
          },
          "extensions": {
            "type": "object",
            "description": "Additional error details and context"
          }
        }
      },
      "bigint": {
        "type": "integer",
        "nullable": true,
        "title": "bigint"
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
---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get Blueprint Execution by ID

Retrieves details of a specific Blueprint Execution by its akUUID

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
    "/blueprint-executions/{id}": {
      "get": {
        "tags": [
          "Blueprints"
        ],
        "summary": "Get Blueprint Execution by ID",
        "description": "Retrieves details of a specific Blueprint Execution by its akUUID",
        "operationId": "getBlueprintExecution",
        "parameters": [
          {
            "required": true,
            "in": "path",
            "name": "id",
            "description": "The akUUID of the Blueprint Execution to retrieve",
            "schema": {
              "$ref": "#/components/schemas/uuid"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Blueprint Execution",
            "content": {
              "application/json": {
                "schema": {
                  "oneOf": [
                    {
                      "type": "object",
                      "title": "Success Response",
                      "properties": {
                        "blueprintExecution": {
                          "$ref": "#/components/schemas/BlueprintExecution"
                        }
                      }
                    },
                    {
                      "type": "array",
                      "title": "Error Response",
                      "description": "Error response (Validation, Not Found)",
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
                      "blueprintExecution": {
                        "akUUID": "cdcc440a-e480-4411-83cb-437d20267a53",
                        "status": "COMPLETED",
                        "inputs": [
                          {
                            "value": "https://cdn.leonardo.ai/users/example/image.png",
                            "nodeId": "9ac3b1e2-4d7f-4f10-8b2f-9e5a1c2d3e4f",
                            "settingName": "imageUrl"
                          },
                          {
                            "value": [
                              {
                                "name": "setting1",
                                "value": "on a bus"
                              }
                            ],
                            "nodeId": "0b5c7344-ccc2-4ee8-9003-8ad3f1a76127",
                            "settingName": "textVariables"
                          }
                        ],
                        "public": false,
                        "createdAt": "2025-11-05T04:51:04.137Z"
                      }
                    }
                  },
                  "badRequest": {
                    "summary": "Bad request error",
                    "value": [
                      {
                        "message": "An error occurred.",
                        "path": [
                          "blueprintExecution"
                        ],
                        "locations": [
                          {
                            "column": 20,
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
                  },
                  "notFound": {
                    "summary": "Not found error",
                    "value": [
                      {
                        "message": "Blueprint execution not found",
                        "path": [
                          "blueprintExecution"
                        ],
                        "locations": [
                          {
                            "column": 20,
                            "line": 1
                          }
                        ],
                        "extensions": {
                          "code": "NOT_FOUND",
                          "errorCode": 0,
                          "statusCode": 404
                        }
                      }
                    ]
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
      "public": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "Whether the generation is public or not"
      },
      "BlueprintExecutionStatus": {
        "type": "string",
        "nullable": false,
        "title": "BlueprintExecutionStatus",
        "enum": [
          "PENDING",
          "QUEUED",
          "COMPLETED",
          "FAILED"
        ],
        "description": "The status of a Blueprint Execution."
      },
      "BlueprintExecution": {
        "type": "object",
        "nullable": false,
        "title": "BlueprintExecution",
        "description": "Represents the Execution of a Blueprint Version",
        "properties": {
          "akUUID": {
            "allOf": [
              {
                "$ref": "#/components/schemas/uuid"
              },
              {
                "nullable": false,
                "description": "akUUID of the Blueprint Execution"
              }
            ]
          },
          "status": {
            "$ref": "#/components/schemas/BlueprintExecutionStatus",
            "description": "Status of the Blueprint Execution"
          },
          "inputs": {
            "type": "array",
            "nullable": false,
            "description": "Inputs of the Blueprint Execution",
            "items": {
              "$ref": "#/components/schemas/NodeInput"
            }
          },
          "public": {
            "allOf": [
              {
                "$ref": "#/components/schemas/public"
              },
              {
                "nullable": false,
                "description": "Whether the Blueprint Execution is public"
              }
            ]
          },
          "createdAt": {
            "$ref": "#/components/schemas/timestamp",
            "description": "Created date of the Blueprint Execution"
          }
        },
        "required": [
          "akUUID",
          "status",
          "inputs",
          "public",
          "createdAt"
        ]
      },
      "timestamp": {
        "type": "string",
        "nullable": false,
        "title": "timestamp"
      },
      "uuid": {
        "nullable": true,
        "pattern": "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}",
        "title": "uuid",
        "type": "string"
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
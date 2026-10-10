---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get Blueprint by ID

Returns a single Blueprint by its akUUID

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
    "/blueprints/{id}": {
      "get": {
        "tags": [
          "Blueprints"
        ],
        "summary": "Get Blueprint by ID",
        "description": "Returns a single Blueprint by its akUUID",
        "operationId": "getBlueprintById",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "description": "The akUUID of the Blueprint to return",
            "schema": {
              "type": "string",
              "format": "uuid"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Blueprint",
            "content": {
              "application/json": {
                "schema": {
                  "oneOf": [
                    {
                      "type": "object",
                      "title": "Success Response",
                      "properties": {
                        "blueprint": {
                          "$ref": "#/components/schemas/Blueprint"
                        }
                      }
                    },
                    {
                      "type": "array",
                      "title": "Error Response",
                      "description": "Error response (validation, not found, etc.)",
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
                      "blueprint": {
                        "akUUID": "c846413e-92ba-4302-84f8-47c667d4761f",
                        "name": "Golden Hour Relight",
                        "description": "Relight an image with warm, golden tones of late afternoon sunlight for a soft and radiant glow.",
                        "thumbnails": [
                          {
                            "name": "thumbnailUrl",
                            "url": "https://cdn.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/goldenhour.jpg"
                          }
                        ],
                        "teamId": null,
                        "official": true,
                        "createdAt": "2025-10-29T21:31:47.999Z",
                        "updatedAt": "2025-12-19T02:34:44.740Z"
                      }
                    }
                  },
                  "badRequest": {
                    "summary": "Bad request error",
                    "value": [
                      {
                        "message": "An error occurred.",
                        "path": [
                          "blueprint"
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
                        "message": "Blueprint not found",
                        "path": [
                          "blueprint"
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
      "Blueprint": {
        "type": "object",
        "title": "Blueprint",
        "description": "A Blueprint object",
        "properties": {
          "akUUID": {
            "type": "string",
            "description": "Unique identifier for the Blueprint",
            "example": "c846413e-92ba-4302-84f8-47c667d4761f"
          },
          "createdAt": {
            "type": "string",
            "format": "date-time",
            "description": "Creation timestamp",
            "example": "2025-10-29T21:31:47.999Z"
          },
          "updatedAt": {
            "type": "string",
            "format": "date-time",
            "description": "Last update timestamp",
            "example": "2025-12-19T02:34:44.740Z"
          },
          "name": {
            "type": "string",
            "description": "Name of the Blueprint",
            "example": "Golden Hour Relight"
          },
          "description": {
            "type": "string",
            "description": "Description of the Blueprint",
            "example": "Relight an image with warm, golden tones of late afternoon sunlight for a soft and radiant glow."
          },
          "thumbnails": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "description": "Thumbnail type name (e.g., thumbnailUrl, videoUrl, thumbnailUrlBanner, thumbnailUrlLandscape, thumbnailUrlExtremePortrait)",
                  "example": "thumbnailUrl"
                },
                "url": {
                  "type": "string",
                  "description": "URL of the thumbnail",
                  "example": "https://cdn.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/goldenhour.jpg"
                }
              }
            }
          },
          "teamId": {
            "type": "string",
            "nullable": true,
            "description": "Team ID if Blueprint belongs to a team",
            "example": null
          },
          "official": {
            "type": "boolean",
            "description": "Whether this is an official Blueprint",
            "example": true
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
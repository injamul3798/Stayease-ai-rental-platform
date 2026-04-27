# StayEase API Contract

## `POST /api/chat/{conversation_id}/message`

### Purpose
Send one guest message to the StayEase chat agent and receive the assistant reply.

### Request Schema
```json
{
  "message": "string",
  "guest_id": "string | null"
}
```

### Response Schema
```json
{
  "conversation_id": "string",
  "intent": "search | details | book | escalate",
  "reply": "string",
  "tool_result": {
    "type": "object"
  },
  "escalated": false
}
```

### Realistic Example
**Request**
```http
POST /api/chat/conv_cxb_001/message
Content-Type: application/json
```

```json
{
  "message": "I need a room in Cox's Bazar from 2026-05-14 to 2026-05-16 for 2 guests",
  "guest_id": "guest_1021"
}
```

**Response**
```json
{
  "conversation_id": "conv_cxb_001",
  "intent": "search",
  "reply": "I found 3 available stays in Cox's Bazar for 2 guests. Beach View Studio is BDT 6,800 per night, Kolatoli Family Suite is BDT 8,500 per night, and Budget Couple Room is BDT 4,900 per night. Tell me the listing ID if you want details or say book to continue.",
  "tool_result": {
    "properties": [
      {
        "listing_id": "SEA-201",
        "title": "Beach View Studio",
        "location": "Cox's Bazar",
        "price_bdt": 6800,
        "currency": "BDT",
        "max_guests": 2,
        "available": true
      },
      {
        "listing_id": "SEA-318",
        "title": "Kolatoli Family Suite",
        "location": "Cox's Bazar",
        "price_bdt": 8500,
        "currency": "BDT",
        "max_guests": 4,
        "available": true
      },
      {
        "listing_id": "SEA-122",
        "title": "Budget Couple Room",
        "location": "Cox's Bazar",
        "price_bdt": 4900,
        "currency": "BDT",
        "max_guests": 2,
        "available": true
      }
    ],
    "count": 3
  },
  "escalated": false
}
```

### Possible Error Responses

#### `400 Bad Request`
```json
{
  "detail": "message must not be empty"
}
```

#### `404 Not Found`
```json
{
  "detail": "conversation not found"
}
```

#### `422 Unprocessable Entity`
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

#### `500 Internal Server Error`
```json
{
  "detail": "internal server error"
}
```

---

## `GET /api/chat/{conversation_id}/history`

### Purpose
Return the stored conversation history for one guest chat thread.

### Response Schema
```json
{
  "conversation_id": "string",
  "messages": [
    {
      "role": "user | assistant",
      "message_text": "string",
      "created_at": "ISO-8601 timestamp"
    }
  ]
}
```

### Realistic Example
**Request**
```http
GET /api/chat/conv_dhk_077/history
```

**Response**
```json
{
  "conversation_id": "conv_dhk_077",
  "messages": [
    {
      "role": "user",
      "message_text": "Show me a place in Dhanmondi for 3 guests from 2026-06-10 to 2026-06-12",
      "created_at": "2026-04-27T09:10:00Z"
    },
    {
      "role": "assistant",
      "message_text": "I found 2 available stays in Dhanmondi. Lake View Apartment is BDT 7,200 per night and City Nest Studio is BDT 5,600 per night.",
      "created_at": "2026-04-27T09:10:02Z"
    }
  ]
}
```

### Possible Error Responses

#### `404 Not Found`
```json
{
  "detail": "conversation not found"
}
```

#### `500 Internal Server Error`
```json
{
  "detail": "internal server error"
}
```

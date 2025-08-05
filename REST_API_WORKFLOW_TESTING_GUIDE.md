# Email Assistant HITL REST API Testing Guide

This guide provides comprehensive workflows for testing the `/process-email-hitl` endpoint with memory features. The system uses three memory namespaces that learn from user interactions:

- **`triage_preferences`**: Learn which emails to ignore/notify/respond to
- **`response_preferences`**: Learn user's email writing style and preferences  
- **`cal_preferences`**: Learn user's meeting scheduling preferences

## 🔧 Prerequisites

1. **Redis Server**: Ensure Redis is running on `localhost:6379`
2. **API Server**: Start the FastAPI server on `localhost:8000`
3. **Base URL**: `http://localhost:8000/process-email-hitl`

## 📋 Core Request/Response Schemas

### Start New Workflow Request
```json
{
  "email": {
    "author": "sender@example.com",
    "to": "lance@langchain.com", 
    "subject": "Email Subject",
    "email_thread": "Email content..."
  }
}
```

### Resume Workflow Request
```json
{
  "thread_id": "uuid-from-previous-response",
  "human_response": {
    "type": "accept|edit|ignore|response",
    "args": { /* optional args for edit/response */ }
  }
}
```

### Response Schema
```json
{
  "status": "interrupted|completed",
  "thread_id": "uuid-string",
  "interrupt": {  // Only when status = "interrupted"
    "action": "tool_name",
    "args": { /* tool arguments */ },
    "description": "Human-readable description",
    "allowed_actions": ["accept", "edit", "ignore", "response"]
  },
  "result": {  // Only when status = "completed"
    "classification": "ignore|notify|respond",
    "response": "Action taken",
    "reasoning": "Why this action was taken"
  }
}
```

---

## 🧪 Testing Workflows

### 1. Triage Memory Learning Workflows

#### 1.1 Teaching Email Classification - "Notify" Decision

**Start: Marketing Email → Human Chooses to Ignore**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "newsletter@techcompany.com",
      "to": "lance@langchain.com",
      "subject": "Weekly Tech Newsletter - AI Updates",
      "email_thread": "Hi Lance,\n\nHere are this weeks top AI developments:\n- GPT-5 announcement\n- New research papers\n\nBest regards,\nTech Newsletter Team"
    }
  }'
```

**Expected Response**: Interrupt with `"action": "Email Assistant: notify"`
```json
{
  "status": "interrupted",
  "thread_id": "uuid-123",
  "interrupt": {
    "action": "Email Assistant: notify",
    "args": {},
    "description": "Email content with classification",
    "allowed_actions": ["ignore", "respond"]
  }
}
```

**Resume: Human Chooses to Ignore**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-123",
    "human_response": {
      "type": "ignore"
    }
  }'
```

**Memory Update**: Updates `triage_preferences` to classify similar newsletters as "ignore"

#### 1.2 Teaching Email Classification - "Respond" Decision

**Start: System Admin Notification → Human Chooses to Respond**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "admin@langchain.com",
      "to": "lance@langchain.com", 
      "subject": "Database Maintenance Window - Action Required",
      "email_thread": "Hi Lance,\n\nWe need to schedule a maintenance window for the production database. Please confirm your availability for this weekend.\n\nBest,\nSysAdmin Team"
    }
  }'
```

**Expected Response**: Interrupt with notification classification

**Resume: Human Provides Feedback to Respond**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-456", 
    "human_response": {
      "type": "response",
      "args": "Please confirm I am available Saturday 2-4 PM for the maintenance window"
    }
  }'
```

**Memory Update**: Updates `triage_preferences` to classify similar admin notifications as "respond"

---

### 2. Response Preferences Learning Workflows

#### 2.1 Teaching Email Writing Style - Edit Response

**Start: Meeting Request Email**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "colleague@langchain.com",
      "to": "lance@langchain.com",
      "subject": "Code Review Meeting - Friday 2PM?", 
      "email_thread": "Hi Lance,\n\nCan we schedule a code review meeting for Friday at 2PM? I have some questions about the new authentication module.\n\nThanks,\nAlex"
    }
  }'
```

**Expected Response**: Email classified as "respond", then interrupt with `write_email` tool

**Resume: Human Edits Email Response**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-789",
    "human_response": {
      "type": "edit",
      "args": {
        "args": {
          "recipient": "colleague@langchain.com",
          "subject": "Re: Code Review Meeting - Friday 2PM?",
          "body": "Hi Alex,\n\nFriday 2PM works perfectly for me. I reviewed the authentication module yesterday and have some notes to share.\n\nLet me know if you need anything specific prepared beforehand.\n\nBest,\nLance"
        }
      }
    }
  }'
```

**Memory Update**: Updates `response_preferences` to learn user's preferred email style and tone

#### 2.2 Teaching Email Response Patterns - Provide Feedback

**Start: Technical Question Email**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "developer@client.com",
      "to": "lance@langchain.com",
      "subject": "API Documentation Question - Missing Endpoint",
      "email_thread": "Hi Lance,\n\nI noticed the API documentation is missing details about the /users/preferences endpoint. Could you provide more information?\n\nThanks,\nDeveloper"
    }
  }'
```

**Expected Response**: Interrupt with `write_email` tool

**Resume: Human Provides Response Feedback**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-012",
    "human_response": {
      "type": "response", 
      "args": "Make sure to acknowledge this is a documentation gap and provide timeline for when it will be updated. Also offer to schedule a call if they need immediate help."
    }
  }'
```

**Memory Update**: Updates `response_preferences` to include patterns for handling technical documentation questions

---

### 3. Calendar Preferences Learning Workflows

#### 3.1 Teaching Meeting Scheduling - Edit Meeting Details

**Start: Meeting Invitation Email**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "manager@langchain.com",
      "to": "lance@langchain.com",
      "subject": "Weekly Team Sync - Scheduling",
      "email_thread": "Hi Lance,\n\nLets schedule our weekly team sync. Are you available next Tuesday at 10 AM for about 45 minutes?\n\nBest,\nManager"
    }
  }'
```

**Expected Response**: Interrupt with `schedule_meeting` tool

**Resume: Human Edits Meeting Details**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-345",
    "human_response": {
      "type": "edit",
      "args": {
        "args": {
          "title": "Weekly Team Sync",
          "participants": ["manager@langchain.com", "lance@langchain.com"],
          "start_time": "2025-08-12T10:00:00",
          "duration_minutes": 30,
          "description": "Weekly team sync - reduced to 30 minutes as requested"
        }
      }
    }
  }'
```

**Memory Update**: Updates `cal_preferences` to prefer 30-minute meetings over 45-minute meetings

#### 3.2 Teaching Meeting Preferences - Ignore Meeting

**Start: Large Group Meeting**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "organizer@langchain.com", 
      "to": "lance@langchain.com",
      "subject": "All-Hands Company Meeting - 2 Hours",
      "email_thread": "Hi Everyone,\n\nWe are scheduling a 2-hour all-hands meeting to discuss company strategy. Please confirm your attendance.\n\nBest,\nOrganizer"
    }
  }'
```

**Expected Response**: Interrupt with `schedule_meeting` tool

**Resume: Human Ignores Long Meeting** 
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-678",
    "human_response": {
      "type": "ignore"
    }
  }'
```

**Memory Update**: Updates `triage_preferences` to classify 2+ hour meetings as low priority

---

### 4. Question Tool Learning Workflows

#### 4.1 Teaching Question Handling - Provide Answer

**Start: Ambiguous Request Email**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "email": {
      "author": "stakeholder@langchain.com",
      "to": "lance@langchain.com", 
      "subject": "Project Update Needed",
      "email_thread": "Hi Lance,\n\nCould you provide an update on the project? We need to know the current status.\n\nThanks,\nStakeholder"
    }
  }'
```

**Expected Response**: Interrupt with `Question` tool asking for clarification

**Resume: Human Answers Question**
```bash
curl -X POST http://localhost:8000/process-email-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "uuid-901",
    "human_response": {
      "type": "response",
      "args": "They want an update on the authentication module project. We are 80% complete, testing phase starts next week."
    }
  }'
```

---

## 🔍 Memory Verification Workflows

### Check Thread State (During Workflow)
```bash
curl -X GET http://localhost:8000/process-email-hitl/{thread_id}
```

### Memory Persistence Test
1. Complete a full workflow with memory updates
2. Restart the API server
3. Send a similar email type - verify the system remembers previous decisions

### Memory Evolution Test
1. Send newsletter → Human ignores → Check triage memory
2. Send different newsletter → Verify auto-classification as "ignore"
3. Send technical email → Human responds → Check response memory  
4. Send similar technical email → Verify improved response quality

---

## 📊 Expected Memory Updates

### Triage Preferences Memory Updates
- **After ignoring newsletters**: Learns to auto-classify promotional emails as "ignore"
- **After responding to admin notifications**: Learns to classify system alerts as "respond"
- **After handling meeting requests**: Learns which meeting types need responses

### Response Preferences Memory Updates  
- **After editing emails**: Learns user's preferred tone, structure, and language style
- **After providing feedback**: Incorporates specific response patterns and requirements
- **After accepting/ignoring responses**: Reinforces or corrects assistant behavior

### Calendar Preferences Memory Updates
- **After editing meeting durations**: Learns preferred meeting lengths
- **After modifying meeting details**: Learns scheduling preferences and constraints
- **After ignoring certain meeting types**: Learns meeting priority patterns

---

## 🚀 Advanced Testing Scenarios

### Scenario 1: Multi-Step Learning
1. Start with default preferences
2. Process 3-5 emails with human feedback
3. Send similar email types to verify learning
4. Check memory evolution through thread state API

### Scenario 2: Memory Conflict Resolution
1. Provide conflicting feedback on similar emails
2. Verify system updates memory appropriately
3. Test edge cases with ambiguous classifications

### Scenario 3: Long-Term Memory Persistence
1. Build up memory over multiple sessions
2. Restart Redis/API services  
3. Verify memory persists and continues learning

This comprehensive guide enables you to test all aspects of the HITL workflow while observing how the system learns and adapts to user preferences through the memory system.

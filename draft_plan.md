# Add Session Archiving to AgentContext

## 1. Write Tests 

- [ ] Test that AgentContext.flush() creates root.json when self.parent_session_id is None
- [ ] Test that AgentContext.flush() creates <session_id>.json when self.parent_session_id is set
- [ ] Test that flush() writes context data to the json file
- [ ] Test that flush() is called after each action in the agent loop
- [ ] Test that flush() is called if the agent loop crashes

## 2. Implement flush() method

- [ ] Add flush() method to AgentContext
- [ ] In flush(), check if self.parent_session_id is None 
    - If so, create ~/.hdev/history/root.json and write context data
    - Else, create ~/.hdev/history/<session_id>.json and write context data
- [ ] Make sure to create ~/.hdev/history directory if it doesn't exist
- [ ] Call flush() at the end of each agent loop iteration 
- [ ] Add try/except around agent loop to call flush() if it crashes

## 3. Update Agent Loop

- [ ] Call context.flush() at the end of each loop iteration
- [ ] Add try/except around loop and call context.flush() if it crashes

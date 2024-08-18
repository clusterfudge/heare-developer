When a coding agent makes multiple edits to a file, the full contents of the file ends up in the context window multiple times. This is wasteful, as it redundantly expresses content already available in the context window, using up input token quotas. 

Instead, let's update our concept of a conversation to have a separate internal representation from that which is sent to the LLM. The internal representation should keep track of which files have been read and modified, and maintain a single copy of the latest state of the file, and a list of structured edits. In the internal conversation, in place of the actual LLM responses related to files,  maintain a reference to the file and the edit.

When rendering a conversation for the LLM, send only the latest version of the file, and in place of the original edit messages include just the diff. 

Create a new directory to keep task descriptions. Create numbered tasks of the format `000-<task description>.md`. Each task should be non-breaking -- the system should continue to function at each step.

Create a set of tasks to complete this project. For each task, create a new task file. For each task, include a description and a set of tests that should be written and pass. 


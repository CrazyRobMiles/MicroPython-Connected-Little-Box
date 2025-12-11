version = "1.0.0"

class Task:

    STATE_RUNNING = "Running"
    STATE_PAUSED = "Paused"
    STATE_FINISHED = "Finished"
    STATE_ERROR = "Error"

    def display_version(self):
        self.output("V1.0 Pre-Alpha")

    def execute_statement(self,statement):

        self.output(f"Executing:{statement}")

        if statement[0]=='*':
            command = statement[1:]
            print(f"Got command:{command}")
            self.clb.handle_command(command)
            return
            
        if len(statement)<2:
            self.output(f"Statement:{statemnent} too short")
            self.state=STATE_ERROR
            return


        command = statement[0:2]

        if command in self.commands:
            self.commands[command]()
        else:
            self.output(f"Command: {command} not found")

    def __init__(self,clb):
        self.clb = clb
        self.commands = { 
            "IV":self.display_version 
            }

    def start_program(self,program_text,output=print):
        self.program_text = program_text
        self.output = output
        self.prog_pos = 0
        self.step_count = 0
        self.state = self.STATE_RUNNING

    def next_statement(self):
        text = self.program_text
        start = self.prog_pos
        end = text.find('\n', start)
        if end == -1:
            return text[start:]  # No newline found, return to end
        return text[start:end]

    def update(self):

        self.step_count = self.step_count+1

        if self.state == self.STATE_RUNNING:
            statement = self.next_statement()
            self.execute_statement(statement)
            self.prog_pos = self.prog_pos + len(statement) + 1
            if self.prog_pos>=len(self.program_text):
                self.state=self.STATE_FINISHED
                return

    def is_running(self):
        return self.state == self.STATE_RUNNING
    

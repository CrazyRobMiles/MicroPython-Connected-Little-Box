version = "1.0.0"

from HullOS.task import Task

class Engine:

    def __init__(self,clb):
        self.clb = clb
        self.tasks = {}

    def start_task(self,task_id,program):
        if task_id in self.tasks:
            task=self.tasks[task_id]
        else:
            task=Task(self.clb)
            self.tasks[task_id]=task
        task.start_program(program)

    def update(self):
        for task in self.tasks.values():
            task.update()

    def active_tasks(self):
        for task in self.tasks.values():
            if task.is_running():
                return True
        return False


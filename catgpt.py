import random

class CatGPT:
    def __init__(self):
        self.chaos = ["*knocks phone off table*", "*sits on touchscreen*", "*meows in binary*"]

    def respond(self, prompt):
        if "food" in prompt.lower():
            return "MEOW! *taps Termux screen* FEED ME."
        elif "code" in prompt.lower():
            return random.choice([
                f"Error: Cat stepped on line {random.randint(1, 100)}.",
                "*purrs* Your code is now 200% fluffier."
            ])
        else:
            return random.choice(self.chaos)

# Run CatGPT
print("🐾 CAT-GPT Activated. Type 'exit' to stop.")
catbot = CatGPT()
while True:
    user_input = input("> ")
    if user_input.lower() == "exit":
        print("*flicks tail* Fine, I’ll nap.")
        break
    print(catbot.respond(user_input))

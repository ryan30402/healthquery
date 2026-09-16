print("Welcome to HealthQuery!")

question = input("Enter a medical information question: ")
question = question.strip()
if question == "":
    print("Please enter a medical information question.")
else:
    print("Your question:", question)

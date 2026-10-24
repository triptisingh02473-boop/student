a=int(input("enter 1st number:"))
b=int(input("enter 2nd number:"))
op=input("enter an operator (+, -, *, /):")
if op=='+':
    print(a+b)
elif op=='-':
    print(a-b)
elif op=='*':
    print(a*b)
elif op=='/':
    if b!=0:
        print(a/b)
    else:
        print("Error: Division by zero")
else:
    print("Invalid operator")

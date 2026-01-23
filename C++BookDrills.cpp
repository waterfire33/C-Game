#include <iostream>
using namespace std;

int main()
{
    cout << "Please enter your name (followed by ENTER):\n"; 
    string first_name;   // first_name is a variable of type string
    cin >> first_name;  // read characters into first_name
    cout << "Hello, " << first_name << "!\n";
    return 0;
}
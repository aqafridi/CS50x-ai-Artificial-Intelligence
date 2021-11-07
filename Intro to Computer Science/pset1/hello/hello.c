#include <stdio.h>
#include <cs50.h>

int main(void)
{
    //getting user name
    string name = get_string("What is your name?\n");
    //printing user name
    printf("hello, %s\n", name);

}
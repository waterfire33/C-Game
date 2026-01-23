#include <iostream>
using namespace std;

struct Node {
    int value;
    Node*left;
    Node*right;

    Node(int v):value(v),left(nullptr),right(nullptr) {}
};
//Visit:Root,Left,Right
void preorder(Node*root){
    if(root == nullptr) return;
    cout<<root->value<<"";
    preorder(root->left);
    preorder(root->right);
} 

//Visit:Left,Right,Root
void postorder(Node*root){
    if(root == nullptr) return;
    postorder(root->left);
    postorder(root->right);
    cout<<root->value<<"";
}

int main (){
    //Build this tree:
    //  1
    // / \
    //2   3

    Node*root = new Node(1);
    root->left = new Node(2);
    root->right = new Node(3);

    cout<<"Preorder: ";
    preorder(root); //123
    cout<<"\n";
    
    cout<<"Postorder: ";
    postorder(root); //231
    cout<<"\n";
    
    //Cleanup (important in C++)
    delete root->left;
    delete root->right;
    delete root;

    return 0;

}

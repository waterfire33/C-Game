#include "Mainwindow.h"
#include "Game.h"
#include "Graphics.h"
#include <SFML/Window/Event.hpp>

int main()
{
    MainWindow wnd( 800, 600, "Chili Framework" );
    Game game( wnd );
    
    while( wnd.IsOpen() )
    {
        // Handle events
        std::optional<sf::Event> event = wnd.GetWindow().pollEvent();
        while( event )
        {
            if( event->is<sf::Event::Closed>() )
            {
                wnd.Close();
            }
            event = wnd.GetWindow().pollEvent();
        }
        
        game.Go();
    }
    
    return 0;
}

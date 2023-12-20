#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT);

int buttons[] = {2, 3, 3, 5, 6, 7}; // Create an array of button pin numbers
bool buttonValues[] = {false, false, false, false, false, false}; // Create an array for button states

typedef enum {
  stopt,
  white_time,
  black_time,
  white_move,
  black_move,
  // ... other states
} State;

State states;

typedef struct {
   int hours;
   int minutes;
   int seconds;
} Time;

Time time_white = {00, 00, 00};
Time time_black = {00, 00, 00};
unsigned long previousMillis = 0;
unsigned int interval = 1000; // Interval for time updates in milliseconds


void printToScreen() {
  display.clearDisplay();
  display.setTextColor( WHITE);
  display.setTextSize(1);
  display.setCursor(3, 3);
  display.println("Black");
  display.setTextSize(3);
  display.setCursor(0, (SCREEN_HEIGHT / 2) - 8);
  display.println("Ready?");
  display.display();
}


void updateButtons() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    buttonValues[i] = digitalRead(buttons[i]);  // Read initial button state
  }
}

void setup() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    pinMode(buttons[i], INPUT_PULLUP);
    buttonValues[i] = digitalRead(buttons[i]); // Read initial button state
  }

  Serial.begin(9600);


  if (!display.begin( SSD1306_SWITCHCAPVCC, 0x3C)) {
    while (true);

  }
  display.clearDisplay();
  display.display();

  states = stopt;
}

void loop() {


  updateButtons();

  switch (states) {
    case stopt:

      if (buttonValues[5] == LOW)  {
        states = white_time;
      }

      break;


    case white_time:
      display.clearDisplay();
      display.setTextColor( WHITE);
      display.setTextSize(3);
      display.setCursor(0, (SCREEN_HEIGHT / 2) - 8);
      display.print(String(time_white.hours) + ":" + String(time_white.minutes) + ":" + String(time_white.seconds));
      display.display();

      

   
 

      break;

    case black_time:

        break;

      case white_move:

          break;

        case black_move:

            break;
          }

}

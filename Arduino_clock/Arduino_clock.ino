#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <avr/io.h>
#include <util/delay.h>

// Define the OLED display parameters for each display
#define SCREEN_WIDTH1 128 // OLED display width, in pixels
#define SCREEN_HEIGHT1 64 // OLED display height, in pixels
#define OLED_RESET1 -1 // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS1 0x3C

Adafruit_SSD1306 display1(SCREEN_WIDTH1, SCREEN_HEIGHT1, &Wire, OLED_RESET1);

// Define the OLED display parameters for the second display
#define SCREEN_WIDTH2 128 // OLED display width, in pixels
#define SCREEN_HEIGHT2 64 // OLED display height, in pixels
#define OLED_RESET2 -1 // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS2 0x3D

Adafruit_SSD1306 display2(SCREEN_WIDTH2, SCREEN_HEIGHT2, &Wire, OLED_RESET2);

// Define the OLED display parameters for the third display
#define SCREEN_WIDTH3 128 // OLED display width, in pixels
#define SCREEN_HEIGHT3 64 // OLED display height, in pixels
#define OLED_RESET3 -1 // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS3 0x3E

Adafruit_SSD1306 display3(SCREEN_WIDTH3, SCREEN_HEIGHT3, &Wire, OLED_RESET3);

int buttons[] = {2, 3, 3, 5, 6, 7}; // Create an array of button pin numbers
bool buttonValues[] = {false, false, false, false, false, false}; // Create an array for button states

int buzzerPin = 8;
int led_White = 9;
int led_Black = 10;

typedef enum {
  start,
  white_time,
  white_increment,
  black_time,
  black_increment,
  white_move,
  black_move,
  finish
} State;

State states;

typedef struct {
  int hours;
  int minutes;
  int seconds;
} Time;

typedef struct {
  int minutes;
  int seconds;
} Increment;


Time time_white               = {00, 00, 00};
Time time_black               = {00, 00, 00};
Increment increment_white     = {00, 00};
Increment increment_black     = {00, 00};
int millis1;
int millis2;


bool PassState;
bool PassState2;

bool black_button = LOW;



void updateButtons() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    buttonValues[i] = digitalRead(buttons[i]);  // Read initial button state
  }
}

void buzzer() {
  if (states == white_move || states == black_move) {
    for (int i = 4; i <= 5; i++) {
      if (buttonValues[i] == LOW) {
        tone(buzzerPin, 1000); // Send a 1kHz tone to the buzzer
        delay(150);
        noTone(buzzerPin);
      }
    }
  }
}


//Control leds
void leds() {
  if (states == white_move || states == black_move) {
    if (states == white_move) {
      digitalWrite(led_White, HIGH);
      digitalWrite(led_Black, LOW);
    } else {
      digitalWrite(led_White, LOW);
      digitalWrite(led_Black, HIGH);
    }
  } else {
    digitalWrite(led_White, LOW);
    digitalWrite(led_Black, LOW);
  }
}


//printWhiteTime
void printWhiteTime() {
  display1.clearDisplay();
  display1.setTextColor( WHITE);
  display1.setTextSize(2);
  display1.setCursor(2, 0);
  display1.print("Time:");
  if (time_white.hours < 10) {
    display1.setCursor(2, (SCREEN_HEIGHT1 / 2) );
    display1.print('0');
    display1.print(time_white.hours);
    display1.print(':');
  } else {
    display1.print(time_white.hours);
    display1.print(':');
  }

  if (time_white.minutes < 10) {
    display1.setCursor(37, (SCREEN_HEIGHT1 / 2) );
    display1.print('0');
    display1.print(time_white.minutes);
    display1.print(':');
  } else {
    display1.print(time_white.minutes);
    display1.print(':');
  }

  if (time_white.seconds < 10) {
    display1.setCursor(72, (SCREEN_HEIGHT1 / 2) );
    display1.print('0');
    display1.print(time_white.seconds);
  } else {
    display1.print(time_white.seconds);
  };
  display1.display();
}


//printBlackTime
void printBlackTime() {
  display2.clearDisplay();
  display2.setTextColor( WHITE);
  display2.setTextSize(2);
  display2.setCursor(2, 0);
  display2.print("Time:");
  if (time_black.hours < 10) {
    display2.setCursor(2, (SCREEN_HEIGHT2 / 2) );
    display2.print('0');
    display2.print(time_black.hours);
    display2.print(':');
  } else {
    display2.print(time_black.hours);
    display2.print(':');
  }

  if (time_black.minutes < 10) {
    display2.setCursor(37, (SCREEN_HEIGHT2 / 2) );
    display2.print('0');
    display2.print(time_black.minutes);
    display2.print(':');
  } else {
    display2.print(time_black.minutes);
    display2.print(':');
  }

  if (time_black.seconds < 10) {
    display2.setCursor(72, (SCREEN_HEIGHT2 / 2) );
    display2.print('0');
    display2.print(time_black.seconds);
  } else {
    display2.print(time_black.seconds);
  };
  display2.display();
}



void setup() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    pinMode(buttons[i], INPUT_PULLUP);
    buttonValues[i] = digitalRead(buttons[i]); // Read initial button state
  }

  Serial.begin(9600);

  pinMode(buzzerPin, OUTPUT);
  pinMode(led_White, OUTPUT);
  pinMode(led_Black, OUTPUT);


  // Initialize the OLED displays
  display1.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS1);
  display2.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS2);
  display3.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS3);

  // Clear the display buffers
  display1.clearDisplay();
  display2.clearDisplay();
  display3.clearDisplay();

  states = start;
}


void loop() {

  updateButtons();
  buzzer();
  leds();
  Serial.println(states);

  switch (states) {

    //Start case
    case start:
      time_white               = {00, 00, 00};
      time_black               = {00, 00, 00};

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_time;
      }


      break;

    //White Time Case
    case white_time:

      if (buttonValues[0] == LOW)  {
        if (!(time_white.seconds == 0 && time_white.minutes == 0 && time_white.hours == 0)) {
          time_white.seconds =  time_white.seconds - 30;

          if ((time_white.seconds < 0)) {
            time_white.seconds = 30;
            time_white.minutes--;
          }

          if (time_white.minutes < 0 && time_white.hours != 0) {
            time_white.seconds = 30;
            time_white.minutes = 59;
            time_white.hours--;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        time_white.seconds =  time_white.seconds + 30;
        if (time_white.seconds >  59) {
          time_white.seconds = 0;
          time_white.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (time_white.minutes > 59 ) {
          time_white.seconds = 0;
          time_white.minutes = 0;
          time_white.hours++;
        }
      }

      printWhiteTime();
      printBlackTime();


      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_increment;
      }

      delay(120);

      break;


    //White increment case
    case white_increment:
      if (buttonValues[0] == LOW)  {
        if (!(increment_white.seconds == 0 && increment_white.minutes == 0)) {
          increment_white.seconds =  increment_white.seconds - 1;

          if ((increment_white.seconds < 0)) {
            increment_white.seconds = 59;
            increment_white.minutes--;
          }

          if (increment_white.minutes < 0 ) {
            increment_white.seconds = 59;
            increment_white.minutes = 59;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        increment_white.seconds =  increment_white.seconds + 1;
        if (increment_white.seconds >  59) {
          increment_white.seconds = 0;
          increment_white.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (increment_white.minutes > 59 ) {
          increment_white.seconds = 0;
          increment_white.minutes = 0;
        }
      }

      display1.clearDisplay();
      display1.setTextColor( WHITE);
      display1.setTextSize(2);
      display1.setCursor(2, 0);
      display1.print("Increment:");

      if (increment_white.minutes < 10) {
        display1.setCursor(2, (SCREEN_HEIGHT1 / 2) );
        display1.print('0');
        display1.print(increment_white.minutes);
        display1.print(':');
      } else {
        display1.print(increment_white.minutes);
        display1.print(':');
      }

      if (increment_white.seconds < 10) {
        display1.setCursor(37, (SCREEN_HEIGHT1 / 2) );
        display1.print('0');
        display1.print(increment_white.seconds);
      } else {
        display1.print(increment_white.seconds);
      };
      display1.display();

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = black_time;
      }

      delay(120);

      break;



    //Black time case
    case black_time:
    
      if (buttonValues[0] == LOW)  {
        if (!(time_black.seconds == 0 && time_black.minutes == 0 && time_black.hours == 0)) {
          time_black.seconds =  time_black.seconds - 30;

          if ((time_black.seconds < 0)) {
            time_black.seconds = 30;
            time_black.minutes--;
          }

          if (time_black.minutes < 0 && time_black.hours != 0) {
            time_black.seconds = 30;
            time_black.minutes = 59;
            time_black.hours--;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        time_black.seconds =  time_black.seconds + 30;
        if (time_black.seconds >  59) {
          time_black.seconds = 0;
          time_black.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (time_black.minutes > 59 ) {
          time_black.seconds = 0;
          time_black.minutes = 0;
          time_black.hours++;
        }
      }

      printWhiteTime();
      printBlackTime();

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = black_increment;
      }

      delay(120);
      break;


    //Black increment case
    case black_increment:

      if (buttonValues[0] == LOW)  {
        if (!(increment_black.seconds == 0 && increment_black.minutes == 0)) {
          increment_black.seconds =  increment_black.seconds - 1;

          if ((increment_black.seconds < 0)) {
            increment_black.seconds = 59;
            increment_black.minutes--;
          }

          if (increment_black.minutes < 0 ) {
            increment_black.seconds = 59;
            increment_black.minutes = 59;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        increment_black.seconds =  increment_black.seconds + 1;
        if (increment_black.seconds >  59) {
          increment_black.seconds = 0;
          increment_black.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (increment_black.minutes > 59 ) {
          increment_black.seconds = 0;
          increment_black.minutes = 0;
        }
      }


      display2.clearDisplay();
      display2.setTextColor( WHITE);
      display2.setTextSize(2);
      display2.setCursor(2, 0);
      display2.print("Increment:");

      if (increment_black.minutes < 10) {
        display2.setCursor(2, (SCREEN_HEIGHT1 / 2) );
        display2.print('0');
        display2.print(increment_black.minutes);
        display2.print(':');
      } else {
        display2.print(increment_black.minutes);
        display2.print(':');
      }

      if (increment_black.seconds < 10) {
        display2.setCursor(37, (SCREEN_HEIGHT1 / 2) );
        display2.print('0');
        display2.print(increment_black.seconds);
      } else {
        display2.print(increment_black.seconds);
      };
      display1.display();



      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_move;


        time_white.seconds = time_white.seconds + increment_white.seconds;
        time_white.minutes = time_white.minutes + increment_white.minutes;

        // Check for seconds overflow
        if (time_white.seconds >= 60) {
          time_white.seconds -= 60;
          time_white.minutes ++;
        }

        // Check for minutes overflow
        if (time_white.minutes >= 60) {
          time_white.minutes -= 60;
          time_white.hours++;
        }

        break;


      //White move case
      case white_move:

        printWhiteTime();
        printBlackTime();


        if (black_button) {
          millis1 = millis();
          black_button = LOW;
        }

        if ((int(millis()) - millis1) > 1000) {
          time_white.seconds --;
          millis1 = 0;
          black_button = HIGH;

          if (time_white.seconds <= 0 && time_white.minutes <= 0 && time_white.hours <= 0) {
            states = finish;
          }

          if ((time_white.seconds < 0)) {
            time_white.seconds = 59;
            time_white.minutes--;
          }

          if (time_white.minutes < 0 && time_white.hours != 0) {
            time_white.seconds = 59;
            time_white.minutes = 59;
            time_white.hours--;
          }
        }

        if (buttonValues[4] == LOW)  {
          PassState = HIGH;
        }

        if (PassState && buttonValues[4] == HIGH) {
          PassState = LOW;
          states = black_move;

          time_white.seconds = time_white.seconds + increment_white.seconds;
          time_white.minutes = time_white.minutes + increment_white.minutes;

          // Check for seconds overflow
          if (time_white.seconds >= 60) {
            time_white.seconds -= 60;
            time_white.minutes ++;
          }

          // Check for minutes overflow
          if (time_white.minutes >= 60) {
            time_white.minutes -= 60;
            time_white.hours++;
          }
        }

        if (buttonValues[2] == LOW)  {
          PassState2 = HIGH;
        }

        if (PassState2 && buttonValues[2] == HIGH) {
          PassState2 = LOW;
          states = finish;
        }

        break;

      case black_move:

        printWhiteTime();
        printBlackTime();


        if (buttonValues[5] == LOW)  {
          PassState = HIGH;
        }

        if (PassState && buttonValues[5] == HIGH) {
          PassState = LOW;
          states = white_move;

          time_black.seconds = time_black.seconds + increment_black.seconds;
          time_black.minutes = time_black.minutes + increment_black.minutes;

          // Check for seconds overflow
          if (time_black.seconds >= 60) {
            time_black.seconds -= 60;
            time_black.minutes ++;
          }

          // Check for minutes overflow
          if (time_black.minutes >= 60) {
            time_black.minutes -= 60;
            time_black.hours++;
          }
        }

        if (buttonValues[3] == LOW)  {
          PassState2 = HIGH;
        }

        if (PassState2 && buttonValues[3] == HIGH) {
          PassState2 = LOW;
          states = finish;
        }

        break;

      case finish:
        printWhiteTime();
        printBlackTime();

        if (buttonValues[2] == LOW)  {
          PassState = HIGH;
        }

        if (PassState && buttonValues[2] == HIGH) {
          PassState = LOW;
          states = start;
        }

        break;

      }

  }
}

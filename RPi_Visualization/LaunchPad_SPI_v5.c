//#############################################################################
//
// FILE:   spi_ex1_loopback.c
//
// TITLE:  SPI Digital Loopback
//
//! \addtogroup driver_example_list
//! <h1>SPI Digital Loopback</h1>
//!
//! This program uses the internal loopback test mode of the SPI module. This
//! is a very basic loopback that does not use the FIFOs or interrupts. A
//! stream of data is sent and then compared to the received stream.
//! The pinmux and SPI modules are configure through the sysconfig file.
//!
//! The sent data looks like this: \n
//!  0000 0001 0002 0003 0004 0005 0006 0007 .... FFFE FFFF 0000
//!
//! This pattern is repeated forever.
//!
//! \b External \b Connections \n
//!  - None
//!
//! \b Watch \b Variables \n
//!  - \b sData - Data to send
//!  - \b rData - Received data
//!
//
//#############################################################################
//
// 
// $Copyright:
// Copyright (C) 2013-2024 Texas Instruments Incorporated - http://www.ti.com/
//
// Redistribution and use in source and binary forms, with or without 
// modification, are permitted provided that the following conditions 
// are met:
// 
//   Redistributions of source code must retain the above copyright 
//   notice, this list of conditions and the following disclaimer.
// 
//   Redistributions in binary form must reproduce the above copyright
//   notice, this list of conditions and the following disclaimer in the 
//   documentation and/or other materials provided with the   
//   distribution.
// 
//   Neither the name of Texas Instruments Incorporated nor the names of
//   its contributors may be used to endorse or promote products derived
//   from this software without specific prior written permission.
// 
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT 
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT 
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT 
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
// $
//#############################################################################

//
// Included Files
//
#include "driverlib.h"
#include "device.h"
#include "board.h"

//
// Interrupt prototypes
//
__interrupt void INT_mySPI0_RX_ISR(void);
__interrupt void INT_mySPI0_TX_ISR(void);
__interrupt void INT_myADCA_1_ISR(void);
__interrupt void INT_myADCB_1_ISR(void);

//
// Global variables
//
uint16_t uVolts = 0; // Send data
uint16_t vVolts = 0; // Send data
uint16_t wVolts = 0; // Send data

uint16_t uAmps = 0; // Send data
uint16_t vAmps = 0; // Send data
uint16_t wAmps = 0; // Send data

volatile uint16_t spi_frame[8];

bool goRead = 0;
bool readA = 0;
bool readB = 0;
uint16_t rData = 0;  // Receive data

uint16_t vRef = 0; // Reference voltage

void update_spi_frame() {
    spi_frame[0] = 0 + 0x0000;
    spi_frame[1] = uVolts + 0x1000;
    spi_frame[2] = vVolts + 0x2000;
    spi_frame[3] = wVolts + 0x7000;
    spi_frame[4] = uAmps + 0xC000;
    spi_frame[5] = vAmps + 0xF000;
    spi_frame[6] = wAmps + 0xA000;
    spi_frame[7] = vRef  + 0x9000;
}

//
// Main
//
void main(void)
{
    //
    // Initialize device clock and peripherals
    //
    Device_init();

    //
    // Disable pin locks and enable internal pullups.
    //
    Device_initGPIO();

    //
    // Initialize PIE and clear PIE registers. Disables CPU interrupts.
    //
    Interrupt_initModule();

    //
    // Initialize the PIE vector table with pointers to the shell Interrupt
    // Service Routines (ISR).
    //
    Interrupt_initVectorTable();

    //
    // Board initialization
    //
    Board_init();

    ADC_enableConverter(myADCA_BASE);
    EPWM_enableADCTrigger(myEPWM2_BASE, EPWM_SOC_A);

    ADC_enableConverter(myADCB_BASE);
    EPWM_enableADCTrigger(myEPWM2_BASE, EPWM_SOC_B);

    //
    // Enable Global Interrupt (INTM) and realtime interrupt (DBGM)
    //
    EINT;
    ERTM;

    //
    // Loop forever. Suspend or place breakpoints to observe the buffers.
    //
    while(1)
    {

    }
}

//
// Data reception ISR
//
__interrupt void INT_mySPI0_RX_ISR(void)
{
    // Block until data is received and then return it
    rData = SPI_readDataBlockingNonFIFO(mySPI0_BASE);

    int i;
    for (i = 0; i < 8; i++) {
        SPI_writeDataBlockingNonFIFO(mySPI0_BASE, spi_frame[i]);
    }

    goRead = 1;
    readA = 0;
    readB = 0;

    Interrupt_clearACKGroup(INTERRUPT_ACK_GROUP6);
}

//
// Data transmission ISR
//
__interrupt void INT_mySPI0_TX_ISR(void)
{
    Interrupt_clearACKGroup(INTERRUPT_ACK_GROUP6);
}

__interrupt void INT_myADCA_1_ISR(void)
{
    if (goRead == 1){
        uVolts = ADC_readResult(myADCA_RESULT_BASE, myADCA_SOC0);
        vVolts = ADC_readResult(myADCA_RESULT_BASE, myADCA_SOC1);
        wVolts = ADC_readResult(myADCA_RESULT_BASE, myADCA_SOC2);
        vRef = ADC_readResult(myADCA_RESULT_BASE, myADCA_SOC3);

        //uVolts = 4008;
        //vVolts = 1445;
        //wVolts = 2121;
        //vRef = 999;

        readA = 1;
    }

    if (readA && readB) {
        update_spi_frame();   // <-- build the frame here
        goRead = 0;           // freeze ADC updates until next SPI cycle
    }

    ADC_clearInterruptStatus(myADCA_BASE, ADC_INT_NUMBER1);

    if (true == ADC_getInterruptOverflowStatus(myADCA_BASE, ADC_INT_NUMBER1)) {
        ADC_clearInterruptOverflowStatus(myADCA_BASE, ADC_INT_NUMBER1);
        ADC_clearInterruptStatus(myADCA_BASE, ADC_INT_NUMBER1);
    }

    Interrupt_clearACKGroup(INTERRUPT_ACK_GROUP1);
}

__interrupt void INT_myADCB_1_ISR(void)
{
    if (goRead == 1){
        uAmps = ADC_readResult(myADCB_RESULT_BASE, myADCB_SOC0);
        vAmps = ADC_readResult(myADCB_RESULT_BASE, myADCB_SOC1);
        wAmps = ADC_readResult(myADCB_RESULT_BASE, myADCB_SOC2);

        //uAmps = 2025;
        //vAmps = 3434;
        //wAmps = 123;

        readB = 1;
    }

    if (readA && readB) {
        update_spi_frame();   // <-- build the frame here
        goRead = 0;           // freeze ADC updates until next SPI cycle
    }

    ADC_clearInterruptStatus(myADCB_BASE, ADC_INT_NUMBER1);

    if (true == ADC_getInterruptOverflowStatus(myADCB_BASE, ADC_INT_NUMBER1)) {
        ADC_clearInterruptOverflowStatus(myADCB_BASE, ADC_INT_NUMBER1);
        ADC_clearInterruptStatus(myADCB_BASE, ADC_INT_NUMBER1);
    }

    Interrupt_clearACKGroup(INTERRUPT_ACK_GROUP1);
}

//
// End File
//

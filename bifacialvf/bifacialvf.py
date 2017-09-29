#!/usr/bin/env python2
# -*- coding: utf-8 -*-
        #          This program calculates irradiances on the front and back surfaces of bifacial PV modules.
        #          Key dimensions and nomenclature:
        #          beta = PV module tilt angle from horizontal, in degrees
        #          sazm = PV module surface azimuth from north, in degrees
        #          1.0 = normalized PV module/panel slant height
        #          C = ground clearance of PV module, in PV module/panel slant heights
        #          D = distance between rows, from rear of module to front of module in next row, in PV module/panel slant heights
        #          h = sin(beta), vertical PV module dimension, in PV module/panel slant heights
        #          x1 = cos(beta), horizontal PV module dimension, in PV module/panel slant heights
        #          rtr = x1 + D, row-to-row distance, from front of module to front of module in next row, in PV module/panel slant heights
        #          cellRows = number of horzontal rows of cells in a PV module/panel
        #          PVfrontSurface = PV module front surface material type, either "glass" or "ARglass"
        #          PVbackSurface = PV module back surfac ematerial type, either "glass" or "ARglass"
        #        
        #         Program flow consists of:
        #          a. Calculate irradiance distribution on ground
        #          b. Calculate AOI corrected irradiance on front of PV module, and irradiance reflected from front of PV module
        #          c. Calculate irradiance on back of PV module
             

 
import math
import csv
import pvlib
import os
#import sys 
#sys.path.insert(0, '../BF_BifacialIrradiances')
from vf import getBackSurfaceIrradiances, getFrontSurfaceIrradiances, getGroundShadeFactors
from vf import getSkyConfigurationFactors, trackingBFvaluescalculator, rowSpacing
from sun import hrSolarPos, perezComp, solarPos, sunIncident



def simulate(TMYtoread, writefiletitle,  beta, sazm, C = 1, D = 0.5,
             rowType = 'interior', transFactor = 0.01, cellRows = 6, 
             PVfrontSurface = 'glass', PVbackSurface = 'glass',  albedo = 0.62,  
             tracking = False, backtrack = False, r2r = 1.5, Cv= 0.05, offset = 0):

    
        ## Read TMY3 data and start loop ~  
        (myTMY3,meta)=pvlib.tmy.readtmy3(TMYtoread)
        #myAxisTitles=myTMY3.axes
        noRows, noCols = myTMY3.shape
        lat = meta['latitude']; lng = meta['longitude']; tz = meta['TZ']
        name = meta['Name']
        
        ## infer the data frequency in minutes
        dataInterval = (myTMY3.index[1]-myTMY3.index[0]).total_seconds()/60
    
        ## Distance between rows for no shading on Dec 21 at 9 am
        print " "
        print "********* "
        print "Running Simulation for TMY3: ", TMYtoread
        print "Location:  ", name
        print "Lat: ", lat, " Long: ", lng, " Tz ", tz
        print "Parameters: beta: ", beta, "  Sazm: ", sazm, "  Height: ", C, "  D separation: ", D, "  Row type: ", rowType, "  Albedo: ", albedo
        print "Saving into", writefiletitle
        print " "
        print " "
        
        DD = rowSpacing(beta, sazm, lat, lng, tz, 9, 0.0);          ## Distance between rows for no shading on Dec 21 at 9 am
        print "Distance between rows for no shading on Dec 21 at 9 am solar time = ", DD
        print "Actual distance between rows = ", D  
        print " "
    
        if tracking==False:        
            ## Sky configuration factors are the same for all times, only based on geometry and row type
            [rearSkyConfigFactors, frontSkyConfigFactors, ffConfigFactors] = getSkyConfigurationFactors(rowType, beta, C, D);       ## Sky configuration factors are the same for all times, only based on geometry and row type
    
     
        ## Create WriteFile and write labels at this time
        
        #check that the save directory exists
        if not os.path.exists(os.path.dirname(writefiletitle)):
            os.makedirs(os.path.dirname(writefiletitle))
        
        with open (writefiletitle,'wb') as csvfile:
            sw = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            # Write Simulation Parameters (from setup file)
            
            if tracking==True:
                Ctype='Vertical GroundClearance(panel slope lengths) Cv'
                Dtype='Row-to-Row-Distance rtr'
                Ctypevar=Cv
                Dtypevar=r2r
            else:
                Ctype='GroundClearance(panel slope lengths)'
                Dtype='DistanceBetweenRows(panel slope lengths)'
                Ctypevar=C
                Dtypevar=D

            outputheader=['Latitude(deg)','Longitude(deg)', 'Time Zone','Tilt(deg)', 
                         'PV Azimuth(deg)',Ctype, Dtype, 'RowType(first interior last single)',
                         'TransmissionFactor(open area fraction)','CellRows(# hor rows in panel)', 
                         'PVfrontSurface(glass or AR glass)', 'PVbackSurface(glass or AR glass)',
                         'CellOffsetFromBack(panel slope lengths)','Albedo',  'Tracking']
            outputheadervars=[lat, lng, tz, beta, sazm, Ctypevar, Dtypevar, rowType, transFactor, cellRows, PVfrontSurface,
                             PVbackSurface, offset, albedo, tracking]
            
            
            if tracking==True:
                outputheader+=['Backtracking']
                outputheadervars.append(backtrack)
                
                
                
            sw.writerow(outputheader)
            sw.writerow(outputheadervars)
            
            # Write Results names"
            allrowfronts=[]
            allrowbacks=[]
            for k in range(0, cellRows):
                allrowfronts.append("No_"+str(k+1)+"_RowFrontGTI")
                allrowbacks.append("No_"+str(k+1)+"_RowBackGTI")      
            outputtitles=['Year', 'Month', 'Day', 'Hour', 'Minute', 'DNI', 'DHI', 
                         'decHRs', 'ghi', 'inc', 'zen', 'azm', 'pvFrontSH', 
                         'aveFrontGroundGHI', 'GTIfrontBroadBand', 'pvBackSH', 
                         'aveBackGroundGHI', 'GTIbackBroadBand', 'maxShadow', 'Tamb', 'Vwind']
            outputtitles+=allrowfronts
            outputtitles+=allrowbacks
            if tracking == True:
                print " ***** IMPORTANT --> THIS SIMULATION Has Tracking Activated"
                print "Backtracking Option is set to: ", backtrack
                outputtitles+=['beta']
                outputtitles+=['height']
                outputtitles+=['D']
                    
            sw.writerow(outputtitles)
            
            ## Loop through file
            rl = 0
            
            while (rl < noRows):
            #while (rl < 8):   # Test while
            #    rl = 8   # Test value
            

                myTimestamp=myTMY3.index[rl]
                year = myTimestamp.year
                month = myTimestamp.month
                day = myTimestamp.day
                hour = myTimestamp.hour
                minute = myTimestamp.minute
                dni = myTMY3.DNI[rl]#get_value(rl,5,"False")
                dhi = myTMY3.DHI[rl]#get_value(rl,8,"False")
                Tamb=myTMY3.DryBulb[rl]#get_value(rl,29,"False")
                Vwind=myTMY3.Wspd[rl]#get_value(rl,44,"False")
           #     
                rl = rl+1   # increasing while count
                            
                azm = 9999.0; zen = 9999.0; elv = 9999.0;
                if (dataInterval == 60):
                    azm, zen, elv, dec, sunrise, sunset, Eo, tst, suntime = hrSolarPos(year, month, day, hour, lat, lng, tz)
                    
                elif (dataInterval == 1 or dataInterval == 5 or dataInterval == 15):
                    azm, zen, elv, dec, sunrise, sunset, Eo, tst = solarPos(year, month, day, hour, minute - 0.5 * dataInterval, lat, lng, tz)
                else :  
                    print("ERROR: data interval not 1, 5, 15, or 60 minutes.");
            
                #123 check abouve this for reading / printing functions
            
                if (zen < 0.5 * math.pi):    # If daylight hours
                
                    # a. CALCULATE THE IRRADIANCE DISTRIBUTION ON THE GROUND *********************************************************************************************
                    #double[] rearGroundGHI = new double[100], frontGroundGHI = new double[100]; ;   # For global horizontal irradiance for each of 100 ground segments, to the rear and front of front of row edge         
                    # Determine where on the ground the direct beam is shaded for a sun elevation and azimuth
                    #int[] rearGroundSH = new int[100], frontGroundSH = new int[100]; # Front and rear row-to-row spacing divided into 100 segments, (later becomes 1 if direct beam is shaded, 0 if not shaded)
                    #double pvFrontSH = 0.0, pvBackSH = 0.0, maxShadow;     # Initialize fraction of PV module front and back surfaces that are shaded to zero (not shaded), and maximum shadow projected from front of row.
                    
                    # TRACKING ROUTINE CALULATING GETSKYCONFIGURATION FACTORS
                    if tracking == True:        
                    
                        daystr=str(day)
                        if day<10:
                            daystr="0"+str(day)
                            
                        monthstr=str(month)
                        if month<10:
                            monthstr="0"+str(month)
                            
                        hourstr = str(hour)
                        if hour<10:
                            hourstr="0"+str(hour)
                            
                        minutestr=str(minute)
                        if minute<10:
                            minutestr="0"+str(minute)
                        
                        if tz >= 0 and tz < 10:
                            tzstr="+0"+str(int(tz))
                        if tz >= 10:
                            tzstr="+"+str(tz)
                        if tz <0 and tz>-10:
                            tzstr="-0"+str(abs(int(tz)))
                        if tz<=-10:
                            tzstr=str(int(tz))
                            
                        times_loc=str(year)+"-"+monthstr+"-"+daystr+" "+hourstr+":"+minutestr+":00"+tzstr+":00"
        
                        solpos = pvlib.solarposition.get_solarposition(times_loc, lat, lng)
                        aazi= solpos['azimuth']
                        azen= solpos['apparent_zenith']
                        axis_tilt = 0
                        axis_azimuth=sazm   # 180 axis N-S
                        max_angle=180
                        
                        gcr=0.2857142857142857  # A value denoting the ground coverage ratio of a tracker system which utilizes backtracking; i.e. the ratio between the PV array surface area to total ground area. A tracker system with modules 2 meters wide, centered on the tracking axis, with 6 meters between the tracking axes has a gcr of 2/6=0.333. If gcr is not provided, a gcr of 2/7 is default. gcr must be <=1.
                        trackingdata = pvlib.tracking.singleaxis(azen, aazi, axis_tilt, axis_azimuth, max_angle, backtrack, gcr)
                                 ## Sky configuration factors are not the same for all times, since the geometry is changing with the tracking.
                        beta=trackingdata.iloc[0][3] # Trackingdata tracker_theta
                        
                        if math.isnan(beta):
                            beta=90
                        #print beta
    
                        # Rotate system if past sun's zenith ~ #123 Check if system breaks withot doing this.
                        if beta<0:
                            sazm = sazm+180    # Rotate detectors
                            beta = -beta;
                            rotatedetectors = True                  
                        [C, D] = trackingBFvaluescalculator(beta, Cv, r2r)
                        [rearSkyConfigFactors, frontSkyConfigFactors, ffConfigFactors] = getSkyConfigurationFactors(rowType, beta, C, D);       ## Sky configuration factors are the same for all times, only based on geometry and row type
    
    
    
                    rearGroundGHI=[]
                    frontGroundGHI=[]
                    pvFrontSH, pvBackSH, maxShadow, rearGroundSH, frontGroundSH = getGroundShadeFactors (rowType, beta, C, D, elv, azm, sazm)
            
                    # Sum the irradiance components for each of the ground segments, to the front and rear of the front of the PV row
                    #double iso_dif = 0.0, circ_dif = 0.0, horiz_dif = 0.0, grd_dif = 0.0, beam = 0.0;   # For calling PerezComp to break diffuse into components for zero tilt (horizontal)                           
                    ghi, iso_dif, circ_dif, horiz_dif, grd_dif, beam = perezComp(dni, dhi, albedo, zen, 0.0, zen)
                    
                    
                    for k in range (0, 100):
                    
                        rearGroundGHI.append(iso_dif * rearSkyConfigFactors[k]);       # Add diffuse sky component viewed by ground
                        if (rearGroundSH[k] == 0):
                            rearGroundGHI[k] += beam + circ_dif;                    # Add beam and circumsolar component if not shaded
                        else:
                            rearGroundGHI[k] += (beam + circ_dif) * transFactor;    # Add beam and circumsolar component transmitted thru module spacing if shaded
            
                        frontGroundGHI.append(iso_dif * frontSkyConfigFactors[k]);     # Add diffuse sky component viewed by ground
                        if (frontGroundSH[k] == 0):
                            frontGroundGHI[k] += beam + circ_dif;                   # Add beam and circumsolar component if not shaded 
                        else:
                            frontGroundGHI[k] += (beam + circ_dif) * transFactor;   # Add beam and circumsolar component transmitted thru module spacing if shaded
                    
            
                    # b. CALCULATE THE AOI CORRECTED IRRADIANCE ON THE FRONT OF THE PV MODULE, AND IRRADIANCE REFLECTED FROM FRONT OF PV MODULE ***************************
                    #double[] frontGTI = new double[cellRows], frontReflected = new double[cellRows];
                    #double aveGroundGHI = 0.0;          # Average GHI on ground under PV array
                    aveGroundGHI, frontGTI, frontReflected = getFrontSurfaceIrradiances(rowType, maxShadow, PVfrontSurface, beta, sazm, dni, dhi, C, D, albedo, zen, azm, cellRows, pvFrontSH, frontGroundGHI)
    
                    #double inc, tiltr, sazmr;
                    inc, tiltr, sazmr = sunIncident(0, beta, sazm, 45.0, zen, azm)	    # For calling PerezComp to break diffuse into components for 
                    save_inc=inc
                    gtiAllpc, iso_dif, circ_dif, horiz_dif, grd_dif, beam = perezComp(dni, dhi, albedo, inc, tiltr, zen)   # Call to get components for the tilt
                    save_gtiAllpc=gtiAllpc
                    #sw.Write(strLine);
                    #sw.Write(",{0,6:0.00}", hour - 0.5 * dataInterval / 60.0 + minute / 60.0);
                    #sw.Write(",{0,6:0.0},{1,5:0.0},{2,5:0.0},{3,5:0.0},{4,4:0.00},{5,6:0.0},{6,6:0.0}",
                        #dni * Math.Cos(zen) + dhi, inc * 180.0 / Math.PI, zen * 180.0 / Math.PI, azm * 180.0 / Math.PI, pvFrontSH, aveGroundGHI, gtiAllpc);
            
                    # CALCULATE THE AOI CORRECTED IRRADIANCE ON THE BACK OF THE PV MODULE,
                    #double[] backGTI = new double[cellRows];
                    backGTI, aveGroundGHI = getBackSurfaceIrradiances(rowType, maxShadow, PVbackSurface, beta, sazm, dni, dhi, C, D, albedo, zen, azm, cellRows, pvBackSH, rearGroundGHI, frontGroundGHI, frontReflected, offset)
               
                    inc, tiltr, sazmr = sunIncident(0, 180.0-beta, sazm-180.0, 45.0, zen, azm)       # For calling PerezComp to break diffuse into components for 
                    gtiAllpc, iso_dif, circ_dif, horiz_dif, grd_dif, beam = perezComp(dni, dhi, albedo, inc, tiltr, zen)   # Call to get components for the tilt
                    
                    
                    ## Write output
                    decHRs = hour - 0.5 * dataInterval / 60.0 + minute / 60.0
                    ghi_calc = dni * math.cos(zen) + dhi 
                    incd = save_inc * 180.0 / math.pi
                    zend = zen * 180.0 / math.pi
                    azmd = azm * 180.0 / math.pi
                    outputvalues=[year, month, day, hour, minute, dni, dhi, decHRs, 
                                  ghi_calc, incd, zend, azmd, pvFrontSH, aveGroundGHI, 
                                  save_gtiAllpc, pvBackSH, aveGroundGHI, 
                                  gtiAllpc, maxShadow, Tamb, Vwind]
                    frontGTIrow=[]
                    backGTIrow=[]
                    for k in range(0, cellRows):
                        frontGTIrow.append(frontGTI[k])
                        backGTIrow.append(backGTI[k])      
                    outputvalues+=frontGTIrow
                    outputvalues+=backGTIrow
                    
                    
                    if tracking==True:
                        outputvalues.append(beta)
                        outputvalues.append(C)
                        outputvalues.append(D)
                                    
                    sw.writerow(outputvalues)
    
        	# End of daylight if loop 
    
        #strLine = sr.ReadLine();        # Read next line of data
       # End of while strLine != null loop
       
     
        print "Finished"
        
        return;
        
if __name__ == "__main__":    

    beta = 10                   # PV tilt (deg)
    sazm = 180                  # PV Azimuth(deg)
    C = 1                      # GroundClearance(panel slope lengths)
    D = 0.51519                 # DistanceBetweenRows(panel slope lengths)
    rowType = "interior"        # RowType(first interior last single)
    transFactor = 0.013         # TransmissionFactor(open area fraction)
    cellRows = 6                # CellRows(# hor rows in panel)   <--> THIS IS FOR LANDSCAPE, YINLI MODEL
    PVfrontSurface = "glass"    #PVfrontSurface(glass or AR glass)
    PVbackSurface = "glass"     # PVbackSurface(glass or AR glass)
    albedo = 0.62               # albedo
    dataInterval = 60           # DataInterval(minutes)
    
    
    # Tracking instructions
    tracking=False
    backtrackingOpt=False
    r2r = 1.5                   # meters. This input is not used (D is used instead) except for in tracking
    Cv = 0.05                  # GroundClearance when panel is in vertical position (panel slope lengths)

    TMYtoread="data/724010TYA.csv"   # VA Richmond
    writefiletitle="data/Output/TEST.csv"
    
    simulate(TMYtoread, writefiletitle, beta, sazm, 
                C, D, rowType, transFactor, cellRows, PVfrontSurface,
                PVbackSurface,  albedo, dataInterval, 
                 tracking, backtrackingOpt, r2r, Cv)
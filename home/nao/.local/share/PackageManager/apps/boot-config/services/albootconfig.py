import time
import traceback
import qi
import sys
import httplib
import os


@qi.multiThreaded()
class ALBootConfig:

    __VERSION__ = "1.0.1"

    DELAY_FOR_ACTIVATE_BA = 30  # sec before activate BA
    MINIMUM_VOLUME = 70  # the minimum volume for the wizard
    ORIENTATION_HELPER_ID = "000_orientation/load_panorama_helper"

    # WIZARD state
    STATE_INIT = "initialized"
    STATE_SYSTEM_UPDATING = "updating"
    STATE_SYSTEM_UPDATED = "updated"
    STATE_FINISHED = "finished"

    # Should be "interactive config" or something.
    CONFIGMODALITY = "com.aldebaran.settings", "InteractiveConfigModality"
    CONFIGMODALITY_TABLETONLY = "TabletOnly"
    CONFIGMODALITY_TABLETORDIALOG = "TabletOrDialog"
    CONFIGMODALITY_DIALOG = "Dialog"
    CONFIGMODALITY_OFF = "NoInteractive"

    UPDATEPOLICY = "com.aldebaran.settings", "Updatepolicy"
    UPDATEPOLICY_AUTOMATIC = "Automatic"
    UPDATEPOLICY_INTERACTIVE = "Interactive"
    UPDATEPOLICY_IGNORE = "Ignore"

    TABLETDEBUGALLOWED = "com.aldebaran.system", "TabletDebugAllowed"
    TABLETDEBUGALLOWED_NO = "0"
    TABLETDEBUGALLOWED_YES = "1"

    AUTOSTARTINTERACTIVECONFIG = "com.aldebaran.settings", "AutostartInteractiveConfig"
    AUTOSTARTINTERACTIVECONFIG_NO = "0"
    AUTOSTARTINTERACTIVECONFIG_YES = "1"

    DISABLELIFEANDDIALOG = "com.aldebaran.debug", "DisableLifeAndDialog"
    DISABLELIFEANDDIALOG_NO = "0"
    DISABLELIFEANDDIALOG_YES = "1"

    MOVEMENTDEACTIVATED = "com.aldebaran.debug", "MovementDeactivated"
    MOVEMENTDEACTIVATED_NO = "0"
    MOVEMENTDEACTIVATED_YES = "1"

    HIDE_SETTINGS_MENU = "com.aldebaran.settings", "HideSettingsMenu"
    HIDE_SETTINGS_MENU_NO = "0"
    HIDE_SETTINGS_MENU_YES = "1"

    DEFAULT_PREFERENCES = {
        CONFIGMODALITY: CONFIGMODALITY_TABLETONLY,
        UPDATEPOLICY: UPDATEPOLICY_IGNORE,
        AUTOSTARTINTERACTIVECONFIG: AUTOSTARTINTERACTIVECONFIG_YES,
        MOVEMENTDEACTIVATED: MOVEMENTDEACTIVATED_NO,
        DISABLELIFEANDDIALOG: DISABLELIFEANDDIALOG_NO,
        TABLETDEBUGALLOWED: TABLETDEBUGALLOWED_NO,
        HIDE_SETTINGS_MENU: HIDE_SETTINGS_MENU_NO
    }

    TABLET_MISSING_NOTIF = {
        "English": "I can't connect to my tablet.",
        "French": "Je ne peux pas me connecter a ma tablette.",
        "Japanese": u"\u30BF\u30D6\u30EC\u30C3\u30C8\u306B\u63A5\u7D9A\u3067\u304D\u307E\u305B\u3093\u3002"
    }

    def __init__(self, session):
        """ ALBootConfig is a service to handle the boot of the robot

        """
        self.session = session

        #logger
        self.logger = qi.logging.Logger("naoqi.core.ALBootconfig")
        self.module = qi.module("qicore")
        self.logManager = self.session.service("LogManager")
        self.provider = self.module.createObject("LogProvider", self.logManager)
        self.providerId = self.logManager.addProvider(self.provider)

        self.logger.info("Starting ...")

        #init variable
        self.checked_interactive = False
        self.checked_tablet = False
        self.is_eula_accepted = False  # EULA Checked
        self.animationOnPageChanged = None  # Animation to play on Page Changed
        #self.syncPrefsTask = None  # Task for wait sync preference
        self.is_online = False  # online or not

        # state variable
        self.isAnimating = False  # Animation is running
        self.isSyncingPrefs = False  # The page synchronizing prefs is displayed
        self.isWaitingTablet = False  # Wait for the page loading
        self.isUpdating = False  # Downloads apps or imagesystem
        self.isUpdatingTablet = False  # Updating the tablet
        self.isAware = True  # activate or not BA

        #services
        self.serviceDirectory = self._get_service("ServiceDirectory")
        if not self.serviceDirectory:
            self.logger.error("ServiceDirectory not found, finishing boot config .....")
            return self.finish()

        self.alconnectionmanager = self._get_service("ALConnectionManager")
        self.alrobotmodel = self._get_service("ALRobotModel")
        self.almemory = self._get_service("ALMemory")
        self.alstore = self._get_service("ALStore")
        self.alpreferencemanager = self._get_service("ALPreferenceManager")
        self.altexttospeech = self._get_service("ALTextToSpeech")
        self.almotion = self._get_service("ALMotion")
        self.packagemanager = self._get_service("PackageManager")
        self.albehaviormanager = self._get_service("ALBehaviorManager")
        self.altabletservice = self._get_service("ALTabletService")

        # subscribe to events/signals
        self._onPreferencesSynchronizedEvent = self.almemory.subscriber("preferenceSynchronized")
        self._onPreferencesSynchronizedEvent.signal.connect(self._onPreferenceSychronized)

        self._onExitMenuEvent = self.almemory.subscriber("RobotsGate/exitMenu")
        self._onExitMenuEvent.signal.connect(self._onExitMenu)

        self.serviceSignal = self.serviceDirectory.serviceAdded.connect(self._handleServiceAdded)
        self.serviceSignalR = self.serviceDirectory.serviceRemoved.connect(self._handleServiceRemoved)

        if self._update_tablet_if_needed():
            self.isUpdatingTablet = True  # Start the tablet update and wait for the ALTabletService reconnection
        else:
            self.run()

    #
    # Animations management
    #
    @qi.nobind
    def _preload_anims(self):
        """ Preload all animations contain in the animations directory"""
        d = os.path.dirname(os.path.abspath(__file__))
        for b in os.listdir(os.path.join(d, "..", "animations")):
            try:
                self.albehaviormanager.preloadBehavior("boot-config/animations/%s" % b)
            except Exception as e:
                self.logger.warning("Unable to preload behavior %s (error : %s" % (b, e))

    @qi.nobind
    def _run_anim(self, animation):
        """ Run an animation contains in the animations directory.
            If an animation is already playing, it will skip.
            If movement is deactivated, the animation will be not played.
            Parameters:
                (String) animation - the animation's name
        """
        if self.isAnimating or self.movement_deactivated:
            return

        self.logger.info("Run animation : %s" % animation)

        self.almotion.setBreathEnabled("Arms", False)

        self.isAnimating = True
        try:
            self.albehaviormanager.runBehavior("boot-config/animations/%s" % animation)
            qi.async(self.albehaviormanager.preloadBehavior, "boot-config/animations/%s" % animation)
        except Exception as e:
            self.logger.error("Unable to play the behavior %s (error: %s)" % (animation, e))

        self.almotion.setBreathEnabled("Arms", True)

        self.isAnimating = False

    @qi.nobind
    def _start_anim_loop(self, animation):
        """ Start an animation contains in animations directory which is in loop, i.e there is no exit call on this animation
            Use self._stop_anim_loop to stop it.
            Parameters:
                (String) Animation - the animation name
        """
        if self.isAnimating or self.movement_deactivated:
            self.logger.info("Don't start anim loop : %s because the robot is already animating" % animation)
            return

        self.isAnimating = True
        self.almotion.setBreathEnabled("Arms", False)
        self.logger.info("Start anim loop : %s" % animation)
        try:
            self.albehaviormanager.startBehavior("boot-config/animations/%s" % animation)
        except Exception as e:
            self.logger.error("Error during starting loop : %s" % e)

    @qi.nobind
    def _stop_anim_loop(self, animation):
        """ Stop an loop animation contains in animations directory.
            Parameters:
                (String) animation - the animation name
        """
        self.logger.info("Stop anim loop : %s" % animation)
        try:
            self.albehaviormanager.stopBehavior("boot-config/animations/%s" % animation)
            qi.async(self.albehaviormanager.preloadBehavior, "boot-config/animations/%s" % animation)
        except Exception as e:
            self.logger.error("Error during stoping update loop : %s" % e)

        self.almotion.setBreathEnabled("Arms", True)
        self.isAnimating = False

    #
    # Helpers
    #
    @qi.nobind
    def _get_service(self, serviceName):
        """ Retrieve a service.
            Parameters:
                (String) serviceName - the name of the service
            Return:
                (Object) The service if it's available, None otherwise
        """
        try:
            return self.session.service(serviceName)
        except Exception as e:
            self.logger.error("error during getting the service %s : %s " % (serviceName, e))
            return None

    @qi.nobind
    def _start_orientation(self):
        self.logger.info("Try to start behavior Orientation ....")
        if self.albehaviormanager.isBehaviorInstalled(ALBootConfig.ORIENTATION_HELPER_ID):
            if not self.albehaviormanager.isBehaviorRunning(ALBootConfig.ORIENTATION_HELPER_ID):
                self.logger.info("Start behavior Orientation")
                self.albehaviormanager.startBehavior(ALBootConfig.ORIENTATION_HELPER_ID)
            else:
                self.logger.info("The behavior Orientation is already running.")
        else:
            self.logger.info("The behavior Orientation is not installed")

    @qi.nobind
    def _iter_needed_upgrades(self):
        for pkginfo in alstore.status():
            pkgdict = dict(pkginfo)
            # The result would be in a form like this:
            #   { "uuid" : "ai-system-install",
            #     "version" : "2.0.0",
            #     "onlineVersion" : "2.0.0",
            #     "status" : 1,
            #     "percent" : -1,
            #     "size" : 27632 }
            if pkgdict["status"] == 3:
                yield pkgdict

    @qi.nobind
    def _is_update_needed(self):
        try:
            for item in self._iter_needed_upgrades():
                return True
            return False
        except Exception as e:
            self.logger.error("Exception while checking packages: %s" % e)
            return False

    @qi.nobind
    def _get_preference(self, valuedef):
        """ Helper to retrieve a preference
            Parameters:
                (tuple) valueDef - tuple with (domain, key)
            Return:
                (Object) The preference value if it exists, the default value (defined in DEFAULT_PREFERENCES), None otherwise
        """
        value = self.alpreferencemanager.getValue(*valuedef)
        if value is not None:
            return value
        else:
            return ALBootConfig.DEFAULT_PREFERENCES.get(valuedef, None)

    @qi.nobind
    def _get_package_version(self, packageID):
        try:
            pkginfo = dict(self.packagemanager.package(packageID))
            if pkginfo:
                return pkginfo.get("version", None)
            else:
                self.logger.warning("No package info for %s: " % packageID)
                return None
        except Exception as e:
            self.logger.error("Couldn't get package info for %s: (error : %s)" % (packageID, e))
            return None

    @qi.nobind
    def _set_state(self, state):
        """ Set the swizard state in preference
            Parameters:
                (String) state - the state
        """
        try:
            self.alpreferencemanager.setValue("com.aldebaran.wizard", "state", state)
        except Exception as e:
            self.logger.error("Unable to change state, error : %s" % e)

    @qi.nobind
    def _get_state(self):
        try:
            return self.alpreferencemanager.getValue("com.aldebaran.wizard", "state")
        except Exception as e:
            self.logger.error("Unable to change state, error : %s" % e)
            return None

    #
    # Services management
    #
    @qi.nobind
    def _handleServiceAdded(self, serviceId, serviceName):
        if serviceName == "ALConnectionManager":
            self.logger.info("ALConnectionManager connected!")
            self.alconnectionmanager = self._get_service("ALConnectionManager")
            self.handleConnectionManagerReady()

        if serviceName == "ALTabletService":
            self.altabletservice = self._get_service("ALTabletService")
            self.logger.info("Tablet reconnected!")
            self.almemory.raiseEvent("Device/DeviceList/Tablet/Error", 0)

            if self.isUpdatingTablet:
                self.isUpdatingTablet = False
                self.run()  # the update tablet is finished
            else:
                self._displayWebView("http://198.18.0.1/")  # Tablet service lost and reconnect

    @qi.nobind
    def _handleServiceRemoved(self, serviceId, serviceName):
        if serviceName == "ALTabletService":
            self.altabletservice = None

    #
    # Network management
    #
    @qi.nobind
    def _checkConnectivity(self):
        """ Check if the robot is online
            If a internet connection is available, it starts the preference update
            Otherwise, it will wait for an event from ALConnectionManager
        """
        is_online = False

        try:
            is_online = (self.alconnectionmanager.state() == "online")
        except Exception as e:
            self.logger.warning("ALConnectionManager not present, acting as if offline. (error : %s)" % e)

        if is_online:
            self._onOnline()
        else:
            self.logger.info("No connection, continuing without synchronizing prefs but wait for network")
            networkStateChangedEvent = self.almemory.subscriber("NetworkStateChanged")
            networkStateChangedEvent.signal.connect(self._onNetworkStateChanged)

    @qi.nobind
    def _onOnline(self):
        if self.is_online:
            return

        self.is_online = True
        self.logger.info("The robot is online, synchronizing prefs...")
        self.alpreferencemanager.update()

    @qi.nobind
    def _onNetworkStateChanged(self, state):
        """ Callback to handle the change of the network """
        self.logger.info("New network state: " + state)
        if state == "online":
            self._onOnline()
        if state == "offline":
            self.is_online = False

    def _onPreferenceSychronized(self, value):
        """ Callback to handle the preference when they just synchronized """
        self.logger.info("Preferences synchronized.")
        self._update_from_preferences()

    @qi.nobind
    def _update_from_preferences(self):
        # 1) Update tablet debug state
        if self.altabletservice:
            if (self._get_preference(ALBootConfig.TABLETDEBUGALLOWED) == ALBootConfig.TABLETDEBUGALLOWED_YES):
                self.logger.info("Enable the debug tablet")
                self.altabletservice._setDebugEnabled(True)
            else:
                self.logger.info("Disable the debug tablet")
                self.altabletservice._setDebugEnabled(False)

        # 2) launch store update
        updatepolicy = self._get_preference(ALBootConfig.UPDATEPOLICY)
        if updatepolicy == ALBootConfig.UPDATEPOLICY_AUTOMATIC:
            self.logger.info("Update policy: automatic; checking ALStore.")
            if self._is_update_needed():
                self.logger.info("Store checked, update needed, starting update ...")
                self.alstore.update()
        else:
            self.logger.info("Update policy: %s; not updating from the store." % str(updatepolicy))

        # 3) Movement deactivated
        movement_deactivated = self._get_preference(ALBootConfig.MOVEMENTDEACTIVATED)
        if movement_deactivated == ALBootConfig.MOVEMENTDEACTIVATED_YES:
            self.movement_deactivated = True
        else:
            self.movement_deactivated = False

    @qi.nobind
    def _check_almemory(self, key):
        try:
            return self.almemory.getData(key)
        except Exception as e:
            # The key doesn't seem to be there: treat as False
            return False

    @qi.nobind
    def _check_and_set_first_launch(self):
        key = "BootConfig/HasStartedAtBoot"
        if self._check_almemory(key):
            return False
        else:  # The key doesn't seem to be there: first launch
            self.almemory.raiseEvent(key, True)
            return True

    @qi.nobind
    def raise_notification(self, notifdic, is_critical):
        self.logger.info("Gave up waiting for tablet, raising notification")

        alnotificationmanager = self._get_service("ALNotificationManager")
        if not alnotificationmanager:
            self.logger.error("Unable to raise a notificatio, ALNotificationManager not found!")
            return

        language = self.altexttospeech.getLanguage()
        if language not in notifdic:
            language = "English"
        message = notifdic[language]
        if is_critical:
            severity = "error"
        else:
            severity = "warning"

        alnotificationmanager.add({"message": message, "severity": severity, "removeOnRead": True})

    #
    # Tablet functions
    #
    @qi.nobind
    def _enable_tablet_wifi(self, enable):
        """Enable/Disable wifi on the tablet"""
        try:
            if enable:
                self.logger.info("Enable the tablet wifi")
                self.altabletservice.enableWifi()
            else:
                self.logger.info("Disable the tablet wifi")
                self.altabletservice.disableWifi()
        except Exception as e:
            self.logger.error("Exception calling ALTabletService.disableWifi(): " + str(e))

    @qi.nobind
    def _displayWebView(self, url):
        """ display the index.html on the tablet """
        if not self.altabletservice:
            self.logger.error("Unable to display the page : %s, ALTabletService not found" % url)
            return

        self._enable_tablet_wifi(False)
        self.altabletservice.loadUrl(url)
        self.altabletservice.showWebview()

    @qi.nobind
    def _displayImage(self, url):
        if not self.altabletservice:
            self.logger.error("Unable to display the image : %s, ALTabletService not found" % url)
            return
        self.altabletservice.preLoadImage(url)
        self.altabletservice.showImage(url)

    @qi.nobind
    def _update_tablet_if_needed(self):
        self.logger.info("[UpdateTablet] Check if tablet update is needed ...")
        packageVersion = self._get_package_version("j-tablet-browser")

        if self.altabletservice:
            launcherVersion = self._get_tablet_launcher_version()
            if launcherVersion is None:
                self.logger.warning("[UpdateTablet] Unable to get the version of the tablet launcher, can't check if update is needed")
                return False

            if (packageVersion != launcherVersion):
                self.logger.info("[UpdateTablet] Launcher uninstall needed: tablet has launcher %s, but package %s is downloaded" % (launcherVersion, packageVersion))
                try:
                    self.logger.info("[UpdateTablet] Start the uninstall apps")
                    qi.async(self.altabletservice._uninstallApps)
                    return True

                except Exception as e:
                    self.logger.error("[UpdateTablet] Uninstall tablet apps failed: %s" % e)
                    return False

            else:
                self.logger.info("[UpdateTablet] Update not needed: tablet has launcher %s, and package %s is downloaded" % (launcherVersion, packageVersion))
                return False
        else:
            self.logger.warning("UpdateTablet] Tablet Launcher update not possible: no ALTabletService.")
            return False

    @qi.nobind
    def _get_tablet_launcher_version(self):
        try:
            return self.altabletservice._launcherVersion()
        except Exception as e:
            self.logger.error("Error during get the tablet launcher version : %s" % e)
            return None

    @qi.nobind
    def _has_tablet(self):
        if self.alrobotmodel._hasTablet():
            return True
        else:
            return False

    @qi.nobind
    def _check_tablet(self):

        if not self._has_tablet():
            return False

        # Report the result to notifications
        if self.altabletservice:
            self.almemory.raiseEvent("Device/DeviceList/Tablet/Error", 0)

        elif self._get_preference(ALBootConfig.CONFIGMODALITY) in (ALBootConfig.CONFIGMODALITY_TABLETONLY, ALBootConfig.CONFIGMODALITY_TABLETORDIALOG):
            # This means that in CONFIGMODALITY_OFF and CONFIGMODALITY_DIALOG, we don't raise a (major) notification here.
            self.logger.error("Gave up waiting for tablet, raising error")
            self.almemory.raiseEvent("Device/DeviceList/Tablet/Error", 1)
            self.raise_notification(ALBootConfig.TABLET_MISSING_NOTIF, True)

        else:
            self.logger.error("Gave up waiting for tablet, but only raising minor error")
            self.almemory.raiseEvent("Device/DeviceList/Tablet/Error", 2)
            self.raise_notification(ALBootConfig.TABLET_MISSING_NOTIF, False)

        return True

    @qi.nobind
    def _install_keyboards(self):
        """ Get a list of availble keyboards  """
        self.logger.info("[UpdateTablet] Install Japanese Keyboard")

        if not self.altabletservice:
            self.logger.error("[UpdateTablet] Unable to install the japanese keyboard, no ALTabletService")
            return

        try:
            keyboards = self.altabletservice.getAvailableKeyboards()
        except Exception as e:
            self.logger.error("Unable to get the available keyboard : %s" % e)
            return

        if "jp.co.omronsoft.iwnnime.ml/.standardcommon.IWnnLanguageSwitcher" not in keyboards:
            self.logger.info("[UpdateTablet] Japanese keyboard not installed, installing ...")
            self.altabletservice._installApk("http://198.18.0.1/apps/boot-config/JapaneseKeyboard.apk")
            self.altabletservice.onApkInstalled.connect(self._onKeyboardInstalled)
        else:
            self.logger.info("[UpdateTablet] Japanese Keyboard already installed")

    @qi.nobind
    def _onApkInstalled(self, data):
        self.logger.info("[UpdateTablet] Keyboard Installed !")

    def getReleaseNotes(self, version, lang):
        """ Retrieve a release note for Naoqi version.
            Parameters:
                version : the version of Naoqi
                lang : the lang to retrieve the release note
        """
        self.logger.info("Retrieve release notes from aldebaran.com (version:%s, lang:%s)" % (version, lang))
        #if not self.is_online:
        #    self.logger.error("Unable to get the release note, the robot is offline")
        #    return None

        self._start_anim_loop("networkLoop")
        try:
            conn = httplib.HTTPConnection("doc.aldebaran.com", timeout=30)
            conn.request("GET", "/releasenotes/%s/%s.html" % (version, lang))
            res = conn.getresponse()
            if res.status != 200:
                raise Exception("Release notes not found !")
        except Exception as e:
            self.logger.error("Unable to retrieve the releasenote : %s" % e)
            self._stop_anim_loop("networkLoop")
            return None

        self._stop_anim_loop("networkLoop")
        return res.read()

    #
    # Robot management
    #
    @qi.nobind
    def _init_ba(self):
        try:
            self.albasicawareness = self._get_service("ALBasicAwareness")
            self.albasicawareness.setEngagementMode("Unengaged")
            self.albasicawareness.setTrackingMode("BodyRotation")
            self.albasicawareness.setStimulusDetectionEnabled('Sound', True)
            self.albasicawareness.setStimulusDetectionEnabled('Movement', False)
            self.albasicawareness.setStimulusDetectionEnabled('People', True)
            self.albasicawareness.setStimulusDetectionEnabled('Touch', False)
            self.baAsyncTask = None
            self.baStarted = False
            self.HumanTrackedEventId = None
        except Exception as e:
            self.logger.error("Error during init Basic Awareness : %s" % e)

    @qi.nobind
    def _start_ba(self):
        if self.isAnimating or not self.isAware:
            return

        self._run_anim("poseInitUp")
        if getattr(self, 'albasicawareness', None):
            self.HumanTrackedEvent = self.almemory.subscriber("ALBasicAwareness/HumanTracked")
            self.HumanTrackedEventId = self.HumanTrackedEvent.signal.connect(self._onHumanTracked)
            self.albasicawareness.startAwareness()

    @qi.nobind
    def _onHumanTracked(self, args):
        self._wait_for_inactivity()
        self._run_anim("inviteTablet")
        self._wait_for_inactivity()

    @qi.nobind
    def _stop_ba(self):
        if getattr(self, 'albasicawareness', None):
            self.albasicawareness.stopAwareness()

    @qi.nobind
    def _wait_for_inactivity(self):
        """Wait for a while before activate Basic awareness"""
        if getattr(self, 'HumanTrackedEventId', None):
            self.HumanTrackedEvent.signal.disconnect(self.HumanTrackedEventId)
            self.HumanTrackedEventId = None

        self._stop_ba()

        if self.baAsyncTask:
            self.baAsyncTask.cancel()
        self.baAsyncTask = qi.async(self._start_ba, delay=ALBootConfig.DELAY_FOR_ACTIVATE_BA*1000000)

    #
    # Misc
    #
    @qi.nobind
    def _subscribe_to_robotwebpage(self):
        self.logger.info("Subscribe to robotwebpage event")
        if not getattr(self, 'pageEventId', None):
            self.pageEvent = self.almemory.subscriber("RobotsGate/pageEvent")
            self.pageEventId = self.pageEvent.signal.connect(self._onPageEvent)

        if not getattr(self, 'pageChangedEventId', None):
            self.pageChangedEvent = self.almemory.subscriber("RobotsGate/pageChanged")
            self.pageChangedEventId = self.pageChangedEvent.signal.connect(self._onPageChangedEvent)

        if not getattr(self, 'touchEventId', None):
            if self.altabletservice:
                self.touchEventId = self.altabletservice.onTouchUp.connect(self._onTouchEvent)

        if not getattr(self, 'inputTextId', None):
            if self.altabletservice:
                self.inputTextId = self.altabletservice.onInputText.connect(self._onInputText)

    @qi.nobind
    def _unsubscribe_to_robotwebpage(self):
        self.logger.info("Unsubscribe to robotwebpage event")
        if self.pageChangedEventId:
            self.pageChangedEvent.signal.disconnect(self.pageChangedEventId)

        if self.pageEventId:
            self.pageEvent.signal.disconnect(self.pageEventId)

        if self.touchEventId:
            self.altabletservice.onTouchUp.disconect(self.touchEventId)

    @qi.nobind
    def _onInputText(self, buttonId, value):
        self.isAware = True
        self._wait_for_inactivity()

    @qi.nobind
    def _onTouchEvent(self, x, y):
        self.logger.info("Touch event")
        self._wait_for_inactivity()

    @qi.nobind
    def _onPageChangedEvent(self, page):
        self.logger.info("onPageChanged : '%s'" % page)

        if self.animationOnPageChanged is not None:
            self._run_anim(self.animationOnPageChanged)
            self.animationOnPageChanged = None

        if self.isWaitingTablet:
            self._stop_anim_loop("turnTabletOn_start")
            self._run_anim("turnTabletOn_end")
            self.isWaitingTablet = False

        if page == "loader":
            self.isSyncingPrefs = True
            self._start_anim_loop("networkLoop")

        if self.isSyncingPrefs or self.isUpdating:
            self.isSyncingPrefs = False
            self.isUpdating = False
            time.sleep(1)
            self._stop_anim_loop("networkLoop")
            self._run_anim("networkOut")

        if page == "endwizard":
            self._stop_ba()
            while(self.isAnimating):
                time.sleep(1)
            self._run_anim("finishWizard")
            self._set_state(ALBootConfig.STATE_FINISHED)

    @qi.nobind
    def _onPageEvent(self, eventName):
        self.logger.info("onPageEvent : %s" % eventName)

        if eventName == "next":
            self.animationOnPageChanged = "onNextPage"

        if eventName == "previous":
            self.animationOnPageChanged = "onPrevPage"

        #EULA
        if eventName == "checkedEULA":
            self._run_anim("ok")

        if eventName == "uncheckedEULA":
            self._run_anim("nok")

        if eventName in ["uncheckedIssueReport", "noUpdateSystem", "network_cancel", "updateIssue"]:
            self._run_anim("nok")

        if eventName in ["checkedIssueReport", "changeLanguage", "changeTimezone", "network_detail", "listNetwork", "manualNetwork", "qrNetwork", "initTouchTablet"]:
            self._run_anim("ok")

        if eventName == "inputText":
            if self.baAsyncTask:
                self.baAsyncTask.cancel()
            self.isAware = False
            return

        # Network
        if eventName == "qrNetwork":
            self._stop_ba()
            return

        if eventName in ["network_configuration", "adeConnecting", "network_connecting"]:
            self._start_anim_loop("networkLoop")

        if eventName in ["network_failure", "network_disconnect"]:
            self._stop_anim_loop("updateLoop")
            self._run_anim("nok")

        if eventName == "updateApp":
            self.isUpdating = True
            self._start_anim_loop("networkLoop")

        if eventName in ["network_ready", "adeSuccess", "updateAppSuccessful"]:
            self._stop_anim_loop("networkLoop")
            self._run_anim("success")

        if eventName == "adeError":
            self._stop_anim_loop("networkLoop")
            self._run_anim("warning")

        if eventName in ["keepRobotPassword", "changeRobotPassword", "closeWindow"]:
            self._run_anim("warningValidate")

        if eventName in ["warningPassword"]:
            self._run_anim("warning")

        #update
        if eventName == "updateSystemNow":
            self.isAware = False
            if self.baAsyncTask:
                self.baAsyncTask.cancel()
            self._start_anim_loop("updateLoop")

        if eventName == "updateSystemError":
            self._stop_anim_loop("updateLoop")

        if eventName == "updateNeeded":
            self._stop_anim_loop("updateLoop")
            self._update()
            return

        if eventName == "chargerPlugged":
            self._run_anim("onPlugged")
            self._run_anim("poseInit")

        if eventName == "chargerUnplugged":
            self._run_anim("onUnPlugged")
            self._run_anim("poseInit")

        # End wizard
        if eventName == "wizard_end_ready":
            self._subscribe_to_robotwebpage()
            self.finish()

        if eventName == "exitMenu":
            self._exit()

    #
    # Run functions
    #
    def run(self):
        """ main run function """
        try:
            self.logger.info("Running startup script ...")

            self._checkConnectivity()
            self._update_from_preferences()

            # Do we launch interactive mode?
            # The rules:
            #     1) When the robot boots, we may or may not show the interactive mode depending on the preferences
            #     2) If NaoQi crashed and restarts, don't show the interactive mode
            #     3) If the behavior has been launched manually (for example by choregraphe, bu runBehavior or switchFocus...),
            #        always show interactive mode
            #     4) If the robot is rebooting after an update, it starts by update applications and finish by launch robotsgate

            # case 4)
            if self._get_state() == ALBootConfig.STATE_SYSTEM_UPDATING:
                self.logger.info("Robot system udapted detected, finish by update applications")
                self._finishUpdate()

            # case 3)
            elif not self._check_and_set_first_launch():
                # The behavior seems to have been manually triggered and not launched during boot.
                self.logger.info("Boot policy: This isn't naoqi-boot's launch (probably launched by runBehavioh or swithFocus), running interactive config.")
                self.run_interactive_config()

            # case 2) set by command-line parameter during auto-reboot
            elif self._check_almemory("naoqi/crashrecovery"):
                self.logger.info("Boot policy: naoqi called with --no-interactive-startup (probably auto-reboot), ignore policy, don't run interactive config.")
                if self._get_preference(("com.aldebaran.robotwebpage", "CurrentPage")) != "menu.root.myrobot":  # GSW not finished
                    self.run_interactive_config()
                else:
                    self.finish()

            # case 1) - check preferences
            elif self._get_preference(ALBootConfig.AUTOSTARTINTERACTIVECONFIG) != ALBootConfig.AUTOSTARTINTERACTIVECONFIG_NO:
                self.logger.info("Boot policy: always run interactive config.")
                self.run_interactive_config()

            else:
                updatepolicy = self._get_preference(ALBootConfig.UPDATEPOLICY)
                if (updatepolicy == ALBootConfig.UPDATEPOLICY_INTERACTIVE) and self._is_update_needed():
                    self.logger.info("Boot policy: running interactive config because updates are needed.")
                    self.run_interactive_config()
                else:
                    self.logger.info("Boot policy: no interactive config, no update prompt needed.")
                    self.finish()

        except Exception as e:
            self.logger.error("Unexpected exception, aborting: %s" % traceback.format_exc())
            self.finish()

    @qi.nobind
    def run_tablet_config(self):

        if not self.movement_deactivated:
            self.almotion.wakeUp()
            self._init_ba()
            self._run_anim("poseInitUp")

        self._subscribe_to_robotwebpage()
        self._displayWebView("http://198.18.0.1/")
        self._start_orientation()

        if not self.movement_deactivated:
            self._start_anim_loop("turnTabletOn_start")
            self.isWaitingTablet = True

    @qi.nobind
    def run_interactive_config(self):
        self._install_keyboards()
        qi.async(self._preload_anims)
        try:
            modality = self._get_preference(ALBootConfig.CONFIGMODALITY)
            self.logger.info("Config modality: %s " % modality)
            if modality == ALBootConfig.CONFIGMODALITY_OFF:
                self.logger.info("No interactive config, exiting.")
                self.finish()
            else:
                if (modality == ALBootConfig.CONFIGMODALITY_TABLETONLY):
                    if self.altabletservice:
                        self.logger.info("Switching to tablet config")
                        self.run_tablet_config()
                    else:
                        self.finish()
                else:
                    self.logger.info("Switching to dialog config, but it's not supported yet .... so finish !")
                    self.finish()

        except Exception as e:
            self.logger.error("Unexpected exception in interactive, aborting: " + repr(e))
            self.finish()

    #
    # Exit function
    #
    @qi.nobind
    def _onStoreUpdated(self):
        self.logger.info("Applications udapted")
        try:
            self.alstore.updated.disconnect(self.applicationUpdateId)
        except Exception as e:
            self.logger.error("Error on store updated : %s" % e)

        if not self.movement_deactivated:
            self._init_ba()
            self.almotion.wakeUp()
            self._run_anim("poseInitUp")

        if self.altabletservice:
            self._subscribe_to_robotwebpage()
            self._displayWebView("http://198.18.0.1/")
        else:
            self.finish()
        self._set_state(ALBootConfig.STATE_SYSTEM_UPDATED)

    @qi.nobind
    def _finishUpdate(self):
        if not self.alstore:
            self.logger.error("Unable to update applications, ALstore not found. Aborting")
            self.finish()
            return

        self.applicationUpdateId = self.alstore.updated.connect(self._onStoreUpdated)
        self.alstore.updateApps()

    @qi.nobind
    def _update(self):
        try:
            self._stop_ba()
            self._run_anim("shutdown")
            self.almotion.rest()
            alsystem = self._get_service("ALSystem")
            if alsystem is None:
                self.logger.error("Unable to reboot the system, ALSystem not found!")
                return
            self._set_state(ALBootConfig.STATE_SYSTEM_UPDATING)
            alsystem.reboot()
        except Exception as e:
            self.logger.error("Unable to reboot, error : %s" % e)

    @qi.nobind
    def _onExitMenu(self, data):
        """ call the event emit by Robotsgate on Exit Menu."""
        self.logger.info("exitMenu raised, quit bootconfig")
        self._exit()

    @qi.nobind
    def _disable_life(self):
        """ Disable life """
        try:
            autonomouslife = self.session.service("ALAutonomousLife")
            autonomouslife.setState("disabled")
        except Exception as e:
            self.logger.error("Error during disabling life : %s" % e)

    @qi.nobind
    def _preload_dialog(self):
        """ Preload the dialog before start life """
        self.logger.info("Preloading dialog...")
        try:
            #TODO : clean relative url
            self._displayWebView("http://198.18.0.1/apps/boot-config/preloading_dialog.html")
            dialog = self.session.service("ALDialog")
            dialog._preloadMain()
            self.altabletservice.hideWebview()
        except Exception as e:
            self.logger.error("Error during preloading the dialog : %s" % e)

    @qi.nobind
    def finish(self):
        self._enable_tablet_wifi(True)

        if (self._get_preference(ALBootConfig.HIDE_SETTINGS_MENU) == ALBootConfig.HIDE_SETTINGS_MENU_YES):
            self.logger.info("Preference set to hide settings menu")
            self._exit()
        elif self._has_tablet():
            self.logger.info("Preference set to show settings menu, display the webpage")
            self._displayWebView("http://198.18.0.1/")
        else:
            self.logger.info("Tablet not detected, exit ...")
            self._exit()

    @qi.nobind
    def _exit(self):
        if (self._get_preference(ALBootConfig.DISABLELIFEANDDIALOG) == ALBootConfig.DISABLELIFEANDDIALOG_YES):
            self.logger.info("The life is set to disabled by preference")
            self._disable_life()
        else:
            self.logger.info("Preloading the dialog ....")
            self._preload_dialog()

        self.logger.info("Stop boot config")
        self.albehaviormanager.stopBehavior("boot-config")

if __name__ == "__main__":
    # get & start application
    application = qi.Application(sys.argv)
    application.start()

    alboot = ALBootConfig(application.session)
    application.session.registerService("ALBootConfig", alboot)

    # block until the session die and/or application.stop() is called
    application.run()

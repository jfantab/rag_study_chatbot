import React, { useState } from 'react';
import {
  Modal,
  View,
  Image,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
  ScrollView,
  SafeAreaView,
  Text,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface ImagePreviewModalProps {
  visible: boolean;
  images: string[];
  initialIndex?: number;
  onClose: () => void;
}

const ImagePreviewModal: React.FC<ImagePreviewModalProps> = ({
  visible,
  images,
  initialIndex = 0,
  onClose,
}) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

  // Update current index when initialIndex changes
  React.useEffect(() => {
    setCurrentIndex(initialIndex);
  }, [initialIndex]);

  const handleScroll = (event: any) => {
    const contentOffsetX = event.nativeEvent.contentOffset.x;
    const newIndex = Math.round(contentOffsetX / screenWidth);
    setCurrentIndex(newIndex);
  };

  return (
    <Modal
      visible={visible}
      transparent={true}
      animationType="fade"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        {/* Dark overlay backdrop */}
        <TouchableOpacity
          style={styles.backdrop}
          activeOpacity={1}
          onPress={onClose}
        >
          {/* Close button */}
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            activeOpacity={0.7}
          >
            <Ionicons name="close" size={30} color="#FFFFFF" />
          </TouchableOpacity>

          {/* Image counter */}
          {images.length > 1 && (
            <View style={styles.counterContainer}>
              <Text style={styles.counterText}>
                {currentIndex + 1} / {images.length}
              </Text>
            </View>
          )}

          {/* Image display */}
          <ScrollView
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onScroll={handleScroll}
            scrollEventThrottle={16}
            contentOffset={{ x: initialIndex * screenWidth, y: 0 }}
            style={styles.scrollView}
            onStartShouldSetResponder={() => true}
          >
            {images.map((imageUri, index) => (
              <View key={index} style={[styles.imageContainer, { width: screenWidth }]}>
                <TouchableOpacity
                  activeOpacity={1}
                  onPress={(e) => e.stopPropagation()}
                  style={styles.imageTouchable}
                >
                  <Image
                    source={{ uri: imageUri }}
                    style={styles.image}
                    resizeMode="contain"
                  />
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>

          {/* Navigation indicators */}
          {images.length > 1 && (
            <View style={styles.indicatorContainer}>
              {images.map((_, index) => (
                <View
                  key={index}
                  style={[
                    styles.indicator,
                    index === currentIndex && styles.indicatorActive,
                  ]}
                />
              ))}
            </View>
          )}
        </TouchableOpacity>
      </SafeAreaView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
  },
  backdrop: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeButton: {
    position: 'absolute',
    top: 50,
    right: 20,
    zIndex: 10,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  counterContainer: {
    position: 'absolute',
    top: 50,
    left: 0,
    right: 0,
    alignItems: 'center',
    zIndex: 5,
  },
  counterText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
  },
  scrollView: {
    flex: 1,
  },
  imageContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  imageTouchable: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    width: '100%',
  },
  image: {
    width: Dimensions.get('window').width,
    height: Dimensions.get('window').height * 0.8,
  },
  indicatorContainer: {
    position: 'absolute',
    bottom: 40,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.5)',
  },
  indicatorActive: {
    backgroundColor: '#FFFFFF',
    width: 24,
  },
});

export default ImagePreviewModal;

import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Modal,
    TouchableOpacity,
    FlatList,
    Alert,
    ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
    Model,
    getAvailableModels,
    getCurrentModel,
    changeModel,
} from '../services/api';

interface ModelSwitcherProps {
    isVisible: boolean;
    onClose: () => void;
    onModelChanged?: (modelName: string) => void;
    onStartNewChat?: () => void;
}

const ModelSwitcher: React.FC<ModelSwitcherProps> = ({
    isVisible,
    onClose,
    onModelChanged,
    onStartNewChat,
}) => {
    const [models, setModels] = useState<Model[]>([]);
    const [currentModelName, setCurrentModelName] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [isChangingModel, setIsChangingModel] = useState<string | null>(null);

    const loadData = async () => {
        try {
            setIsLoading(true);
            const [modelsData, currentModelData] = await Promise.all([
                getAvailableModels(),
                getCurrentModel(),
            ]);

            setModels(modelsData);
            setCurrentModelName(currentModelData.current_model_name || '');
        } catch (error) {
            console.error('Error loading model data:', error);
            Alert.alert('Error', 'Failed to load model information');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (isVisible) {
            loadData();
        }
    }, [isVisible]);

    const handleModelSelect = async (model: Model) => {
        if (model.name === currentModelName) {
            return; // Already selected
        }

        try {
            setIsChangingModel(model.name);
            const response = await changeModel(model.name);

            if (response.success) {
                setCurrentModelName(model.name);
                onModelChanged?.(model.name);

                // Start a new chat when model changes
                onStartNewChat?.();

                Alert.alert(
                    'Model Changed',
                    `Successfully switched to ${model.name}. A new chat has been started.`,
                    [{ text: 'OK', onPress: onClose }]
                );
            } else {
                Alert.alert('Error', 'Failed to change model');
            }
        } catch (error) {
            console.error('Error changing model:', error);
            Alert.alert('Error', 'Failed to change model. Please try again.');
        } finally {
            setIsChangingModel(null);
        }
    };

    const renderModelItem = ({ item }: { item: Model }) => {
        const isSelected = item.name === currentModelName;
        const isChanging = isChangingModel === item.name;

        return (
            <TouchableOpacity
                style={[
                    styles.modelItem,
                    isSelected && styles.selectedModelItem,
                ]}
                onPress={() => handleModelSelect(item)}
                disabled={isChanging || isSelected}
            >
                <View style={styles.modelItemContent}>
                    <View style={styles.modelInfo}>
                        <Text
                            style={[
                                styles.modelName,
                                isSelected && styles.selectedModelName,
                            ]}
                            numberOfLines={1}
                        >
                            {item.name}
                        </Text>
                        <Text style={styles.modelCategory}>
                            {item.category}
                        </Text>
                    </View>

                    <View style={styles.modelStatus}>
                        {isChanging ? (
                            <ActivityIndicator size="small" color="#007AFF" />
                        ) : isSelected ? (
                            <View style={styles.selectedBadge}>
                                <Ionicons
                                    name="checkmark"
                                    size={16}
                                    color="#FFFFFF"
                                />
                            </View>
                        ) : null}
                    </View>
                </View>
            </TouchableOpacity>
        );
    };

    const groupedModels = models.reduce((acc, model) => {
        if (!acc[model.category]) {
            acc[model.category] = [];
        }
        acc[model.category].push(model);
        return acc;
    }, {} as Record<string, Model[]>);

    return (
        <Modal
            visible={isVisible}
            animationType="slide"
            presentationStyle="pageSheet"
            onRequestClose={onClose}
        >
            <SafeAreaView style={styles.container}>
                <View style={styles.header}>
                    <Text style={styles.headerTitle}>Select Model</Text>
                    <TouchableOpacity
                        style={styles.closeButton}
                        onPress={onClose}
                    >
                        <Ionicons name="close" size={24} color="#333" />
                    </TouchableOpacity>
                </View>

                {isLoading ? (
                    <View style={styles.loadingContainer}>
                        <ActivityIndicator size="large" color="#007AFF" />
                        <Text style={styles.loadingText}>
                            Loading models...
                        </Text>
                    </View>
                ) : (
                    <FlatList
                        data={Object.entries(groupedModels)}
                        keyExtractor={([category]) => category}
                        renderItem={({ item: [category, categoryModels] }) => (
                            <View style={styles.categorySection}>
                                <Text style={styles.categoryTitle}>
                                    {category}
                                </Text>
                                {categoryModels.map((model) => (
                                    <View key={model.id}>
                                        {renderModelItem({ item: model })}
                                    </View>
                                ))}
                            </View>
                        )}
                        showsVerticalScrollIndicator={false}
                        contentContainerStyle={styles.listContent}
                    />
                )}

                <View style={styles.footer}>
                    <Text style={styles.footerText}>
                        Current: {currentModelName || 'Loading...'}
                    </Text>
                </View>
            </SafeAreaView>
        </Modal>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 20,
        paddingVertical: 16,
        borderBottomWidth: 1,
        borderBottomColor: '#E0E0E0',
    },
    headerTitle: {
        fontSize: 25,
        fontWeight: '600',
        color: '#333',
    },
    closeButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        fontSize: 16,
        color: '#666',
        marginTop: 12,
    },
    listContent: {
        paddingVertical: 16,
    },
    categorySection: {
        marginBottom: 24,
    },
    categoryTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#333',
        paddingHorizontal: 20,
        marginBottom: 12,
    },
    modelItem: {
        paddingHorizontal: 20,
        paddingVertical: 16,
        borderBottomWidth: 1,
        borderBottomColor: '#F0F0F0',
    },
    selectedModelItem: {
        backgroundColor: '#F0F8FF',
        borderBottomColor: '#007AFF',
    },
    modelItemContent: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    modelInfo: {
        flex: 1,
    },
    modelName: {
        fontSize: 16,
        fontWeight: '500',
        color: '#333',
        marginBottom: 4,
    },
    selectedModelName: {
        color: '#007AFF',
    },
    modelCategory: {
        fontSize: 14,
        color: '#666',
    },
    modelStatus: {
        marginLeft: 12,
    },
    selectedBadge: {
        width: 24,
        height: 24,
        borderRadius: 12,
        backgroundColor: '#007AFF',
        justifyContent: 'center',
        alignItems: 'center',
    },
    footer: {
        paddingHorizontal: 20,
        paddingVertical: 16,
        borderTopWidth: 1,
        borderTopColor: '#E0E0E0',
        backgroundColor: '#F8F9FA',
    },
    footerText: {
        fontSize: 14,
        color: '#666',
        textAlign: 'center',
    },
});

export default ModelSwitcher;
